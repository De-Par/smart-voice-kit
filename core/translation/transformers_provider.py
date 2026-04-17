from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from time import perf_counter

from core.language import normalize_language_code
from core.translation.base import BaseTranslationEngine
from schemas.runtime import ModelPreparationResult
from schemas.transcription import TranslationResult

logger = logging.getLogger(__name__)


class BaseTransformersTranslationEngine(BaseTranslationEngine, ABC):
    provider_name = "transformers"

    def __init__(
        self,
        model_name: str,
        *,
        model_path: Path | None = None,
        download_root: Path | None = None,
        local_files_only: bool = True,
        source_language: str | None = None,
        target_language: str = "en",
        cpu_threads: int = 0,
        max_length: int = 256,
        device: str = "auto",
    ) -> None:
        self.model_name = model_name
        self.model_path = model_path
        self.download_root = download_root
        self.local_files_only = local_files_only
        self.source_language = self.normalize_language_code(source_language)
        self.target_language = self.normalize_language_code(target_language) or "en"
        self.cpu_threads = cpu_threads
        self.max_length = max_length
        self.device = device
        self._tokenizer = None
        self._model = None

    @property
    def model_source(self) -> str:
        if self.model_path is not None:
            return str(self.model_path)
        return self.model_name

    def normalize_language_code(self, value: str | None) -> str | None:
        return normalize_language_code(value)

    def _get_components(self):
        if self._tokenizer is not None and self._model is not None:
            return self._tokenizer, self._model

        try:
            import torch
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as error:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "Translation runtime requires `transformers`, `sentencepiece`, and a supported "
                "PyTorch installation."
            ) from error

        self._configure_torch_runtime(torch)
        model_device = self._resolve_device(torch)
        logger.info(
            "Initializing translation family=%s provider=%s model_source=%s device=%s "
            "cpu_threads=%s local_files_only=%s download_root=%s",
            self.family_name,
            self.provider_name,
            self.model_source,
            model_device,
            self.cpu_threads,
            self.local_files_only,
            self.download_root,
        )

        source = self.model_path or self.model_name
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                source,
                cache_dir=self.download_root,
                local_files_only=self.local_files_only,
            )
            self._model = AutoModelForSeq2SeqLM.from_pretrained(
                source,
                cache_dir=self.download_root,
                local_files_only=self.local_files_only,
            )
        except Exception as error:
            if self.local_files_only:
                raise RuntimeError(
                    "Local translation model is not available. Run "
                    "`ivoice-install-model configured` once with internet access or set "
                    "`translation.model_path`."
                ) from error
            raise

        self._model.to(model_device)
        self._model.eval()
        return self._tokenizer, self._model

    def _configure_torch_runtime(self, torch_module) -> None:
        if self.cpu_threads <= 0:
            return
        try:
            torch_module.set_num_threads(self.cpu_threads)
        except Exception:  # pragma: no cover - torch runtime boundary
            logger.warning(
                "Failed to apply translation cpu_threads=%s for model=%s",
                self.cpu_threads,
                self.model_name,
            )

    def _resolve_device(self, torch_module) -> str:
        if self.device != "auto":
            return self.device
        if torch_module.cuda.is_available():
            return "cuda"
        mps = getattr(torch_module.backends, "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
        return "cpu"

    def prepare(self) -> ModelPreparationResult:
        self._get_components()
        return ModelPreparationResult(
            task="translation",
            family=self.family_name,
            provider=self.provider_name,
            model_name=self.model_name,
            model_source=self.model_source,
            download_root=str(self.download_root) if self.download_root is not None else None,
            local_files_only=self.local_files_only,
            ready=True,
            mode="verified",
        )

    def translate(
        self,
        text: str,
        *,
        source_language: str | None = None,
        target_language: str = "en",
    ) -> TranslationResult:
        effective_source_language = (
            self.normalize_language_code(source_language) or self.source_language
        )
        effective_target_language = (
            self.normalize_language_code(target_language) or self.target_language
        )

        if not text.strip():
            return TranslationResult(
                text="",
                source_language=effective_source_language,
                target_language=effective_target_language,
                inference_seconds=0.0,
                translation_family=self.family_name,
                translation_provider=self.provider_name,
                model_name=self.model_name,
            )

        tokenizer, model = self._get_components()
        self.validate_language_pair(
            source_language=effective_source_language,
            target_language=effective_target_language,
        )

        try:
            import torch
        except ImportError as error:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "PyTorch is required for the configured translation runtime."
            ) from error

        generate_kwargs = {"max_length": self.max_length}
        generate_kwargs.update(
            self.build_generate_kwargs(
                tokenizer=tokenizer,
                source_language=effective_source_language,
                target_language=effective_target_language,
            )
        )

        started_at = perf_counter()
        inputs = tokenizer(text, return_tensors="pt", truncation=True)
        model_device = next(model.parameters()).device
        inputs = {key: value.to(model_device) for key, value in inputs.items()}

        with torch.no_grad():
            output = model.generate(**inputs, **generate_kwargs)
        translated_text = tokenizer.decode(output[0], skip_special_tokens=True).strip()

        return TranslationResult(
            text=translated_text,
            source_language=effective_source_language,
            target_language=effective_target_language,
            inference_seconds=perf_counter() - started_at,
            translation_family=self.family_name,
            translation_provider=self.provider_name,
            model_name=self.model_name,
        )

    def validate_language_pair(
        self,
        *,
        source_language: str | None,
        target_language: str,
    ) -> None:
        return None

    @abstractmethod
    def build_generate_kwargs(
        self,
        *,
        tokenizer,
        source_language: str | None,
        target_language: str,
    ) -> dict[str, int]:
        raise NotImplementedError
