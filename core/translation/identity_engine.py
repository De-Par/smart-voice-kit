from __future__ import annotations

from time import perf_counter

from core.language import normalize_language_code
from core.translation.base import BaseTranslationEngine
from schemas.runtime import ModelPreparationResult
from schemas.transcription import TranslationResult


class IdentityTranslationEngine(BaseTranslationEngine):
    family_name = "identity"
    provider_name = "identity"

    def __init__(self, model_name: str = "identity-en-pass") -> None:
        self.model_name = model_name

    def prepare(self) -> ModelPreparationResult:
        return ModelPreparationResult(
            task="translation",
            family=self.family_name,
            provider=self.provider_name,
            model_name=self.model_name,
            model_source=self.model_name,
            local_files_only=True,
            ready=True,
            mode="builtin",
        )

    def normalize_language_code(self, value: str | None) -> str | None:
        return normalize_language_code(value)

    def translate(
        self,
        text: str,
        *,
        source_language: str | None = None,
        target_language: str = "en",
    ) -> TranslationResult:
        started_at = perf_counter()
        return TranslationResult(
            text=text.strip(),
            source_language=self.normalize_language_code(source_language),
            target_language=self.normalize_language_code(target_language) or "en",
            inference_seconds=perf_counter() - started_at,
            translation_family=self.family_name,
            translation_provider=self.provider_name,
            model_name=self.model_name,
        )
