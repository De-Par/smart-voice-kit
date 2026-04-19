from __future__ import annotations

import logging
from pathlib import Path

from core.asr.base import BaseASREngine
from core.audio import (
    copy_audio_file,
    ensure_wav_path,
    get_audio_overview,
    maybe_normalize_audio,
    save_uploaded_audio,
)
from schemas.command import CommandNormalizationResult
from schemas.command_run import CommandRun
from schemas.config import AppSettings
from schemas.model import ModelRequest
from services.command_normalization import CommandNormalizationService
from services.command_run_builder import CommandRunBuilder
from services.run_service import RunInputTarget, RunService
from services.run_store import RunArtifactStore

logger = logging.getLogger(__name__)


class AudioCommandService:
    def __init__(
        self,
        *,
        settings: AppSettings,
        asr_engine: BaseASREngine,
        asr_request: ModelRequest,
        command_normalization_service: CommandNormalizationService,
        run_store: RunArtifactStore,
        run_service: RunService,
        run_builder: CommandRunBuilder,
    ) -> None:
        self.settings = settings
        self.asr_engine = asr_engine
        self.asr_request = asr_request
        self.command_normalization_service = command_normalization_service
        self.run_store = run_store
        self.run_service = run_service
        self.run_builder = run_builder

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        filename: str | None = None,
        language: str | None = None,
    ) -> CommandRun:
        target = self.run_service.create_target()
        logger.info(
            "Saving uploaded audio for run_id=%s filename=%s",
            target.run_id,
            filename or "input.wav",
        )
        save_uploaded_audio(audio_bytes, target.audio_path)
        return self._process_run_audio(target, language=language)

    def transcribe_file(
        self,
        source_path: str | Path,
        language: str | None = None,
    ) -> CommandRun:
        source = ensure_wav_path(Path(source_path))
        target = self.run_service.create_target()
        logger.info("Copying source audio for run_id=%s source=%s", target.run_id, source)
        copy_audio_file(source, target.audio_path)
        return self._process_run_audio(target, language=language)

    def transcribe_existing_run_audio(
        self,
        run_dir: str | Path,
        audio_path: str | Path,
        language: str | None = None,
    ) -> CommandRun:
        target = self.run_service.build_existing_audio_target(run_dir, audio_path)
        return self._process_run_audio(target, language=language)

    def transcribe_last(self, language: str | None = None) -> CommandRun:
        latest_audio_path = self.run_service.get_last_audio_path()
        return self.transcribe_file(latest_audio_path, language=language)

    def _process_run_audio(
        self,
        target: RunInputTarget,
        *,
        language: str | None = None,
    ) -> CommandRun:
        normalized_audio_path = maybe_normalize_audio(target.audio_path)
        effective_target = target
        if normalized_audio_path != target.audio_path:
            effective_target = RunInputTarget(
                run_id=target.run_id,
                timestamp=target.timestamp,
                run_dir=target.run_dir,
                audio_path=normalized_audio_path,
            )
        return self._transcribe_saved_audio(effective_target, language=language)

    def _transcribe_saved_audio(
        self,
        target: RunInputTarget,
        *,
        language: str | None = None,
    ) -> CommandRun:
        effective_language = language or self.settings.asr.language

        try:
            duration_seconds, sample_rate = get_audio_overview(target.audio_path)
            logger.info(
                "Starting transcription run_id=%s family=%s provider=%s model=%s",
                target.run_id,
                self.asr_engine.family_name,
                self.asr_engine.provider_name,
                self.asr_engine.model_name,
            )
            transcription = self.asr_engine.transcribe(
                target.audio_path,
                language=effective_language,
            )
            normalization_result = self._normalize_audio_command(
                transcription.transcript,
                asr_language=transcription.language,
            )
        except Exception:
            logger.exception("Speech pipeline failed for run_id=%s", target.run_id)
            raise

        artifacts = self.run_store.build_artifacts(
            run_dir=target.run_dir,
            audio_path=target.audio_path,
        )
        self.run_store.write_command_artifacts(
            artifacts=artifacts,
            source_text=transcription.transcript,
            normalized_text=normalization_result.normalized.text,
            normalization_result=normalization_result,
        )

        metadata = self.run_builder.build_metadata(
            artifacts=artifacts,
            run_id=target.run_id,
            timestamp=target.timestamp,
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            source_text=transcription.transcript,
            source_modality="audio",
            normalization_result=normalization_result,
            inference_seconds=transcription.inference_seconds,
            asr_family=transcription.asr_family,
            asr_provider=transcription.asr_provider,
            asr_model_name=transcription.model_name,
        )
        self.run_store.write_metadata(artifacts, metadata)

        logger.info(
            "Completed speech pipeline run_id=%s duration=%.2fs asr=%.2fs translation=%s",
            target.run_id,
            duration_seconds,
            transcription.inference_seconds,
            (
                f"{normalization_result.normalized.translation_inference_seconds:.2f}s"
                if normalization_result.normalized.translation_inference_seconds is not None
                else f"<{normalization_result.normalized.status}>"
            ),
        )

        return self.run_store.build_run(artifacts, metadata)

    def _normalize_audio_command(
        self,
        source_text: str,
        *,
        asr_language: str | None,
    ) -> CommandNormalizationResult:
        try:
            return self.command_normalization_service.normalize_command(
                source_text,
                modality="audio",
                language=asr_language,
                fallback_language=self.settings.translation.source_language,
                allow_detection=False,
                allow_segmented_fallback=True,
                source_if_explicit="asr",
                source_if_fallback="config",
            )
        except RuntimeError as error:
            logger.warning("Command normalization stage skipped: %s", error)
            return self.command_normalization_service.build_error_result(
                source_text,
                modality="audio",
                message=str(error),
                normalized_text=source_text,
                language=asr_language,
                language_source="asr" if asr_language else "config",
            )
