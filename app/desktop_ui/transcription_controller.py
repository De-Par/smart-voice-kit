from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from app.desktop_ui.qt import QMessageBox, QObject, QThread, Slot
from app.desktop_ui.tasks import BackgroundTask
from schemas.runtime import PipelinePreparationResult
from schemas.transcription import TranscriptionRun

if TYPE_CHECKING:
    from app.desktop_ui.window import VoiceDesktopWindow


class DesktopTranscriptionController(QObject):
    def __init__(self, window: VoiceDesktopWindow) -> None:
        super().__init__(window)
        self.window = window

    @Slot()
    def transcribe_current_audio(self) -> None:
        if self.window.context is None:
            QMessageBox.information(
                self.window,
                "Initializing",
                "The local runtime is still starting. Please wait a moment.",
            )
            return
        if self.window._worker_kind == "transcribe":
            self.request_stop_transcription()
            return
        if self.window.current_audio_path is None or not self.window.current_audio_path.exists():
            QMessageBox.information(self.window, "No audio", "Record or open a WAV file first.")
            return
        if self.window._record_finalize_path is not None:
            QMessageBox.information(
                self.window,
                "Audio is not ready",
                "The recording is still being finalized. Please wait a moment.",
            )
            return

        language = self.window.language_input.text().strip() or None
        audio_path = self.window.current_audio_path
        cold_start = getattr(self.window.context.service.asr_engine, "_model", None) is None
        self.run_background(
            fn=lambda: self.transcribe_with_auto_prepare(audio_path, language),
            on_success=self.show_transcription_result,
            busy_message="Preparing models" if cold_start else "Transcribing",
            kind="transcribe",
        )

    def run_background(
        self,
        fn: Callable[[], object],
        on_success: Callable[[object], None],
        busy_message: str,
        kind: str | None = None,
    ) -> None:
        if self.window._worker_thread is not None:
            QMessageBox.information(self.window, "Busy", "Another operation is already running.")
            return

        self.window._worker_kind = kind
        self.window._discard_worker_result = False
        self.window._show_notification(busy_message, tone="warning", animate=True, auto_hide_ms=0)
        self.window._set_controls_enabled(False)

        thread = QThread(self.window)
        worker = BackgroundTask(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(self.show_error)
        worker.failed.connect(thread.quit)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.clear_worker)

        self.window._worker_thread = thread
        self.window._worker = worker
        thread.start()

    @Slot(object)
    def show_transcription_result(self, result: object) -> None:
        prepare_payload = None
        if isinstance(result, dict):
            prepare_payload = result.get("prepare")
            if prepare_payload is not None:
                self.window.last_prepare_result = PipelinePreparationResult.model_validate(
                    prepare_payload
                )
            result = result["run"]

        if self.window._discard_worker_result:
            self.window._discard_worker_result = False
            self.window._hide_notification()
            self.window._refresh_details_panel()
            return

        self.window.last_run = TranscriptionRun.model_validate(result)
        self.window.transcript_box.setPlainText(self.window.last_run.metadata.transcript)
        self.window.copy_button.setEnabled(bool(self.window.last_run.metadata.transcript.strip()))
        if prepare_payload is not None:
            skipped_components = [
                component
                for component in self.window.last_prepare_result.components
                if component.mode == "skipped"
            ]
            self.window._show_notification(
                "Check details" if skipped_components else "Models ready",
                tone="success",
                auto_hide_ms=1800,
            )
        else:
            self.window._show_notification("Done", tone="success", auto_hide_ms=1400)
        self.window._refresh_details_panel()

    @Slot(str)
    def show_error(self, message: str) -> None:
        self.window._show_notification("Task failed", tone="error", auto_hide_ms=0)
        QMessageBox.critical(self.window, "Operation failed", message)

    @Slot()
    def clear_worker(self) -> None:
        self.window._worker_thread = None
        self.window._worker = None
        self.window._worker_kind = None
        self.window._set_controls_enabled(True)

    def request_stop_transcription(self) -> None:
        self.window._discard_worker_result = True
        self.window.transcribe_button.setEnabled(False)
        self.window._show_notification("Stopping", tone="warning", animate=True, auto_hide_ms=0)

    def transcribe_with_auto_prepare(
        self,
        audio_path: Path,
        language: str | None,
    ) -> dict[str, object]:
        if self.window.context is None:
            raise RuntimeError("Desktop runtime is not initialized yet.")
        try:
            if self.window.current_run_dir is not None and audio_path.is_relative_to(
                self.window.current_run_dir
            ):
                run = self.window.context.service.transcribe_existing_run_audio(
                    self.window.current_run_dir,
                    audio_path,
                    language=language,
                )
            else:
                run = self.window.context.service.transcribe_file(audio_path, language=language)
            return {"run": run}
        except RuntimeError as error:
            recoverable_errors = (
                "Local speech model is not available",
                "Local translation model is not available",
            )
            if not any(message in str(error) for message in recoverable_errors):
                raise

        prepare_result = self.window.context.service.prepare_pipeline_assets()
        if self.window.current_run_dir is not None and audio_path.is_relative_to(
            self.window.current_run_dir
        ):
            run = self.window.context.service.transcribe_existing_run_audio(
                self.window.current_run_dir,
                audio_path,
                language=language,
            )
        else:
            run = self.window.context.service.transcribe_file(audio_path, language=language)
        return {
            "run": run,
            "prepare": prepare_result,
        }
