from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.language import LanguageDetectionError, normalize_language_code
from schemas.command import CommandNormalizationResult
from schemas.command_run import CommandMetadata, CommandRun
from schemas.config import AppSettings
from schemas.model import ModelRequest
from services.command_normalization import CommandNormalizationService
from services.command_run_builder import CommandRunBuilder
from services.run_service import RunService
from services.run_store import RunArtifactStore


class TextCommandService:
    def __init__(
        self,
        *,
        settings: AppSettings,
        asr_request: ModelRequest,
        command_normalization_service: CommandNormalizationService,
        run_store: RunArtifactStore,
        run_service: RunService,
        run_builder: CommandRunBuilder,
    ) -> None:
        self.settings = settings
        self.asr_request = asr_request
        self.command_normalization_service = command_normalization_service
        self.run_store = run_store
        self.run_service = run_service
        self.run_builder = run_builder

    def normalize_text_input(
        self,
        text: str,
        *,
        language: str | None = None,
    ) -> CommandRun:
        target = self.run_service.create_target()
        return self._write_text_run(
            run_dir=target.run_dir,
            text=text,
            timestamp=target.timestamp,
            audio_path="",
            language=language,
            existing_metadata=None,
        )

    def update_run_source_text(
        self,
        run_dir: str | Path,
        source_text: str,
        *,
        language: str | None = None,
    ) -> CommandRun:
        resolved_run_dir = Path(run_dir).expanduser().resolve()
        existing_metadata = self.run_service.load_metadata(resolved_run_dir)
        return self._write_text_run(
            run_dir=resolved_run_dir,
            text=source_text,
            timestamp=existing_metadata.timestamp,
            audio_path=existing_metadata.audio_path,
            language=language,
            existing_metadata=existing_metadata,
        )

    def normalize_command_text(
        self,
        text: str,
        *,
        language: str | None = None,
        fallback_language: str | None = None,
    ) -> CommandNormalizationResult:
        return self.command_normalization_service.normalize_command(
            text,
            modality="text",
            language=language,
            fallback_language=(
                fallback_language
                or self.settings.translation.source_language
                or self.settings.asr.language
            ),
            allow_detection=language is None,
            allow_segmented_fallback=language is None,
            source_if_explicit="explicit",
            source_if_fallback="config",
        )

    def _normalize_manual_command(
        self,
        source_text: str,
        *,
        explicit_language: str | None,
        fallback_language: str | None,
        existing_command_en: str,
    ) -> CommandNormalizationResult:
        try:
            return self.command_normalization_service.normalize_command(
                source_text,
                modality="text",
                language=explicit_language,
                fallback_language=fallback_language,
                allow_detection=explicit_language is None,
                source_if_explicit="explicit",
                source_if_fallback="config",
            )
        except LanguageDetectionError as error:
            return self.command_normalization_service.build_error_result(
                source_text,
                modality="text",
                message=str(error),
                normalized_text=existing_command_en,
                language=None,
                language_source="unknown",
            )
        except RuntimeError as error:
            return self.command_normalization_service.build_error_result(
                source_text,
                modality="text",
                message=str(error),
                normalized_text=existing_command_en,
                language=explicit_language or fallback_language,
                language_source="explicit" if explicit_language else "config",
            )

    def _write_text_run(
        self,
        *,
        run_dir: Path,
        text: str,
        timestamp: datetime,
        audio_path: str,
        language: str | None,
        existing_metadata: CommandMetadata | None,
    ) -> CommandRun:
        artifacts = self.run_store.build_artifacts(
            run_dir=run_dir,
            audio_path=audio_path,
        )

        normalized_source_text = text.strip()
        if not normalized_source_text:
            raise ValueError("Source cmd cannot be empty.")

        explicit_language = normalize_language_code(language)
        fallback_language = (
            normalize_language_code(existing_metadata.language)
            if existing_metadata is not None and existing_metadata.language is not None
            else self.settings.translation.source_language or self.settings.asr.language
        )
        normalization_result = self._normalize_manual_command(
            normalized_source_text,
            explicit_language=explicit_language,
            fallback_language=fallback_language,
            existing_command_en=(
                existing_metadata.command_en
                if existing_metadata is not None
                else normalized_source_text
            ),
        )
        self.run_store.write_command_artifacts(
            artifacts=artifacts,
            source_text=normalized_source_text,
            normalized_text=normalization_result.normalized.text,
            normalization_result=normalization_result,
        )

        existing_id = existing_metadata.id if existing_metadata is not None else run_dir.name
        updated_metadata = self.run_builder.build_metadata(
            artifacts=artifacts,
            run_id=existing_id,
            timestamp=timestamp,
            duration_seconds=0.0,
            sample_rate=1,
            source_text=normalized_source_text,
            source_modality="text",
            normalization_result=normalization_result,
            inference_seconds=0.0,
            asr_family=self.asr_request.descriptor.family,
            asr_provider=self.asr_request.descriptor.provider,
            asr_model_name=self.asr_request.descriptor.model_name,
            existing_metadata=existing_metadata,
        )
        self.run_store.write_metadata(artifacts, updated_metadata)

        return self.run_store.build_run(artifacts, updated_metadata)
