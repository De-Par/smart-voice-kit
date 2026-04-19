from __future__ import annotations

import logging

from core.language import (
    LanguageDetectionError,
    analyze_text_language_spans,
    detect_text_language,
    detect_text_script,
    normalize_language_code,
)
from core.pcs.base import BasePCSEngine
from core.text_cleanup import clean_command_text
from schemas.command import (
    CommandNormalizationResult,
    CommandSource,
    CommandSpan,
    LanguageResolution,
    NormalizedCommand,
    PCSNormalizationResult,
)
from schemas.config import AppSettings
from schemas.runtime import ModelPreparationResult
from services.span_normalization import SpanNormalizationService
from services.translation_router import TranslationRouter

logger = logging.getLogger(__name__)


class CommandNormalizationService:
    def __init__(
        self,
        settings: AppSettings,
        translation_router: TranslationRouter,
        pcs_engine: BasePCSEngine | None = None,
    ) -> None:
        self.settings = settings
        self.translation_router = translation_router
        self.pcs_engine = pcs_engine
        self.span_normalization_service = SpanNormalizationService(translation_router)

    def warm_up_components(self) -> list[ModelPreparationResult]:
        components: list[ModelPreparationResult] = []
        for route in self.translation_router.iter_routes():
            engine = self.translation_router.get_engine(route)
            try:
                components.append(engine.prepare())
            except RuntimeError as error:
                components.append(
                    ModelPreparationResult(
                        task="translation",
                        family=route.descriptor.family,
                        provider=route.descriptor.provider,
                        model_name=route.descriptor.model_name,
                        model_source=route.descriptor.model_name,
                        download_root=(
                            str(route.descriptor.download_root)
                            if route.descriptor.download_root is not None
                            else None
                        ),
                        local_files_only=route.descriptor.local_files_only,
                        ready=False,
                        mode="skipped",
                        message=str(error),
                    )
                )
        if self.settings.pcs.enabled and self.pcs_engine is not None:
            try:
                components.append(self.pcs_engine.prepare())
            except RuntimeError as error:
                components.append(
                    ModelPreparationResult(
                        task="pcs",
                        family=self.settings.pcs.family,
                        provider=self.settings.pcs.provider,
                        model_name=self.settings.pcs.model_name,
                        model_source=self.settings.pcs.model_name,
                        download_root=(
                            str(self.settings.pcs.download_root)
                            if self.settings.pcs.download_root is not None
                            else None
                        ),
                        local_files_only=self.settings.pcs.local_files_only,
                        ready=False,
                        mode="skipped",
                        message=str(error),
                    )
                )
        return components

    def resolve_language(
        self,
        text: str,
        *,
        language: str | None = None,
        fallback_language: str | None = None,
        allow_detection: bool = True,
        source_if_explicit: str = "explicit",
        source_if_fallback: str = "fallback",
    ) -> LanguageResolution:
        explicit_language = normalize_language_code(language)
        if explicit_language is not None:
            return LanguageResolution(language=explicit_language, source=source_if_explicit)

        if allow_detection:
            detected_language = detect_text_language(text)
            return LanguageResolution(language=detected_language, source="detected")

        fallback = normalize_language_code(fallback_language)
        if fallback is not None:
            return LanguageResolution(language=fallback, source=source_if_fallback)

        return LanguageResolution(language=None, source="unknown")

    def normalize_command(
        self,
        text: str,
        *,
        modality: str,
        language: str | None = None,
        fallback_language: str | None = None,
        allow_detection: bool = True,
        allow_segmented_fallback: bool = False,
        source_if_explicit: str = "explicit",
        source_if_fallback: str = "fallback",
    ) -> CommandNormalizationResult:
        source_text = clean_command_text(text)
        if not source_text:
            raise ValueError("Command text cannot be empty.")

        target_language = normalize_language_code(self.settings.translation.target_language) or "en"
        if allow_segmented_fallback and self._should_prefer_span_normalization(source_text):
            return self._finalize_result(
                self.span_normalization_service.normalize(
                    source_text,
                    modality=modality,
                    target_language=target_language,
                )
            )
        try:
            resolution = self.resolve_language(
                source_text,
                language=language,
                fallback_language=fallback_language,
                allow_detection=allow_detection,
                source_if_explicit=source_if_explicit,
                source_if_fallback=source_if_fallback,
            )
        except LanguageDetectionError as error:
            if language is not None:
                raise
            message = str(error).lower()
            if "mixed scripts" in message or "ambiguous" in message:
                return self._finalize_result(
                    self.span_normalization_service.normalize(
                        source_text,
                        modality=modality,
                        target_language=target_language,
                    )
                )
            raise

        command_source = CommandSource(
            text=source_text,
            modality=modality,
            language=resolution.language,
            language_source=resolution.source,
        )

        if not self.settings.translation.enabled:
            return self._finalize_result(
                CommandNormalizationResult(
                    source=command_source,
                    normalized=NormalizedCommand(
                        text=source_text,
                        target_language=target_language,
                        status="disabled",
                        message="Translation is disabled.",
                    ),
                    spans=[
                        CommandSpan(
                            text=source_text,
                            kind="text",
                            language=resolution.language,
                            language_source=resolution.source,
                            status="disabled",
                            normalized_text=source_text,
                        )
                    ],
                )
            )

        if resolution.language is not None and resolution.language == target_language:
            return self._finalize_result(
                CommandNormalizationResult(
                    source=command_source,
                    normalized=NormalizedCommand(
                        text=source_text,
                        target_language=target_language,
                        status="skipped",
                        message="Command already matches target language.",
                        preserved_span_count=1,
                    ),
                    spans=[
                        CommandSpan(
                            text=source_text,
                            kind="text",
                            language=resolution.language,
                            language_source=resolution.source,
                            status="kept",
                            normalized_text=source_text,
                        )
                    ],
                )
            )

        try:
            translation = self.translation_router.translate(
                source_text,
                source_language=resolution.language,
                target_language=target_language,
            )
        except RuntimeError:
            if language is not None and not allow_segmented_fallback:
                raise
            return self._finalize_result(
                self.span_normalization_service.normalize(
                    source_text,
                    modality=modality,
                    target_language=target_language,
                )
            )

        return self._finalize_result(
            CommandNormalizationResult(
                source=command_source,
                normalized=NormalizedCommand(
                    text=translation.text,
                    target_language=translation.target_language,
                    status="translated",
                    translated_span_count=1,
                    translation_family=translation.translation_family,
                    translation_provider=translation.translation_provider,
                    translation_model_name=translation.model_name,
                    translation_inference_seconds=translation.inference_seconds,
                ),
                spans=[
                    CommandSpan(
                        text=source_text,
                        kind="text",
                        language=resolution.language,
                        language_source=resolution.source,
                        status="translated",
                        normalized_text=translation.text,
                        translation_family=translation.translation_family,
                        translation_provider=translation.translation_provider,
                        translation_model_name=translation.model_name,
                    )
                ],
            )
        )

    def build_error_result(
        self,
        text: str,
        *,
        modality: str,
        message: str,
        normalized_text: str,
        language: str | None = None,
        language_source: str = "unknown",
    ) -> CommandNormalizationResult:
        target_language = normalize_language_code(self.settings.translation.target_language) or "en"
        default_route = self.translation_router.default_route.descriptor
        return self._finalize_result(
            CommandNormalizationResult(
                source=CommandSource(
                    text=text,
                    modality=modality,
                    language=normalize_language_code(language),
                    language_source=language_source,
                ),
                normalized=NormalizedCommand(
                    text=normalized_text,
                    target_language=target_language,
                    status="error",
                    message=message,
                    translation_family=default_route.family,
                    translation_provider=default_route.provider,
                    translation_model_name=default_route.model_name,
                ),
                spans=[
                    CommandSpan(
                        text=text,
                        kind="text",
                        language=normalize_language_code(language),
                        language_source=language_source,
                        status="error",
                        normalized_text=normalized_text,
                        translation_family=default_route.family,
                        translation_provider=default_route.provider,
                        translation_model_name=default_route.model_name,
                    )
                ],
            )
        )

    def _finalize_result(self, result: CommandNormalizationResult) -> CommandNormalizationResult:
        cleaned_normalized_text = clean_command_text(result.normalized.text)
        pcs_result = self._apply_pcs(cleaned_normalized_text, result=result)
        normalized = result.normalized.model_copy(
            update={
                "text": pcs_result.text,
                "pcs_status": pcs_result.status,
                "pcs_message": pcs_result.message,
                "pcs_family": pcs_result.pcs_family,
                "pcs_provider": pcs_result.pcs_provider,
                "pcs_model_name": pcs_result.pcs_model_name,
                "pcs_inference_seconds": pcs_result.inference_seconds,
            }
        )
        return result.model_copy(update={"normalized": normalized})

    def _apply_pcs(
        self,
        text: str,
        *,
        result: CommandNormalizationResult,
    ) -> PCSNormalizationResult:
        if not text:
            return PCSNormalizationResult(
                text="",
                status="skipped",
                message="Nothing to post-process.",
            )
        if not self.settings.pcs.enabled or self.pcs_engine is None:
            return PCSNormalizationResult(
                text=text,
                status="disabled",
                message="PCS post-processing is disabled.",
            )
        if not self._should_apply_pcs(result):
            return PCSNormalizationResult(
                text=text,
                status="skipped",
                message="PCS post-processing is only applied to English-ready commands.",
            )
        try:
            return self.pcs_engine.normalize_text(text)
        except RuntimeError as error:
            logger.warning("PCS post-processing skipped: %s", error)
            return PCSNormalizationResult(
                text=text,
                status="error",
                message=str(error),
                pcs_family=self.settings.pcs.family,
                pcs_provider=self.settings.pcs.provider,
                pcs_model_name=self.settings.pcs.model_name,
            )

    def _should_apply_pcs(self, result: CommandNormalizationResult) -> bool:
        target_language = result.normalized.target_language
        if target_language != "en":
            return False
        if result.normalized.status == "translated":
            return True
        return (
            result.normalized.status in {"skipped", "disabled"}
            and result.source.language == target_language
        )

    def _should_prefer_span_normalization(self, text: str) -> bool:
        scripts = {
            detect_text_script(span.text)
            for span in analyze_text_language_spans(text)
            if span.kind == "text"
        }
        scripts.discard("other")
        scripts.discard("mixed")
        return len(scripts) > 1
