from __future__ import annotations

from pathlib import Path

from rich.console import Console

from core.asr.base import BaseASREngine
from schemas.command import CommandNormalizationResult
from schemas.command_run import CommandRun
from schemas.config import AppSettings
from schemas.model import ModelRequest
from schemas.runtime import ModelPreparationResult, PipelinePreparationResult
from services.audio_command_service import AudioCommandService
from services.command_normalization import CommandNormalizationService
from services.command_run_builder import CommandRunBuilder
from services.prepare_model import prepare_configured_models, prepare_model
from services.run_service import RunService
from services.run_store import RunArtifactStore
from services.text_command_service import TextCommandService


class CommandService:
    def __init__(
        self,
        *,
        settings: AppSettings,
        asr_engine: BaseASREngine,
        asr_request: ModelRequest,
        command_normalization_service: CommandNormalizationService,
        run_store: RunArtifactStore,
        run_service: RunService,
    ) -> None:
        self.settings = settings
        self.asr_engine = asr_engine
        self.asr_request = asr_request
        self.command_normalization_service = command_normalization_service
        self.run_store = run_store
        self.run_service = run_service
        self.run_builder = CommandRunBuilder()
        self.audio = AudioCommandService(
            settings=settings,
            asr_engine=asr_engine,
            asr_request=asr_request,
            command_normalization_service=command_normalization_service,
            run_store=run_store,
            run_service=run_service,
            run_builder=self.run_builder,
        )
        self.text = TextCommandService(
            settings=settings,
            asr_request=asr_request,
            command_normalization_service=command_normalization_service,
            run_store=run_store,
            run_service=run_service,
            run_builder=self.run_builder,
        )

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        filename: str | None = None,
        language: str | None = None,
    ) -> CommandRun:
        return self.audio.transcribe_bytes(audio_bytes, filename=filename, language=language)

    def transcribe_file(
        self,
        source_path: str | Path,
        language: str | None = None,
    ) -> CommandRun:
        return self.audio.transcribe_file(source_path, language=language)

    def transcribe_existing_run_audio(
        self,
        run_dir: str | Path,
        audio_path: str | Path,
        language: str | None = None,
    ) -> CommandRun:
        return self.audio.transcribe_existing_run_audio(run_dir, audio_path, language=language)

    def transcribe_last(self, language: str | None = None) -> CommandRun:
        return self.audio.transcribe_last(language=language)

    def normalize_text_input(
        self,
        text: str,
        *,
        language: str | None = None,
    ) -> CommandRun:
        return self.text.normalize_text_input(text, language=language)

    def update_run_source_text(
        self,
        run_dir: str | Path,
        source_text: str,
        *,
        language: str | None = None,
    ) -> CommandRun:
        return self.text.update_run_source_text(run_dir, source_text, language=language)

    def normalize_command_text(
        self,
        text: str,
        *,
        language: str | None = None,
        fallback_language: str | None = None,
    ) -> CommandNormalizationResult:
        return self.text.normalize_command_text(
            text,
            language=language,
            fallback_language=fallback_language,
        )

    def prepare_asr_assets(
        self,
        *,
        force_download: bool = False,
        console: Console | None = None,
    ) -> ModelPreparationResult:
        request = self.asr_request.model_copy(update={"force_download": force_download})
        return prepare_model(request, console=console)

    def prepare_pipeline_assets(
        self,
        *,
        force_download: bool = False,
        console: Console | None = None,
    ) -> PipelinePreparationResult:
        return prepare_configured_models(
            self.settings,
            force_download=force_download,
            console=console,
        )

    def warm_up_asr(self) -> ModelPreparationResult:
        return self.asr_engine.prepare()

    def warm_up_pipeline(self) -> PipelinePreparationResult:
        components = [self.asr_engine.prepare()]
        if self.settings.translation.enabled or self.settings.pcs.enabled:
            components.extend(self.command_normalization_service.warm_up_components())
        return PipelinePreparationResult(components=components)

    def prepare_asr(self) -> ModelPreparationResult:
        return self.warm_up_asr()
