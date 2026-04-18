from __future__ import annotations

from pathlib import Path

from app.desktop_ui.audio_controller import DesktopAudioController
from app.desktop_ui.helpers import build_details_text
from app.desktop_ui.qt import (
    QApplication,
    QAudioInput,
    QAudioOutput,
    QMainWindow,
    QMediaCaptureSession,
    QMediaPlayer,
    QMediaRecorder,
    Qt,
    QThread,
    QTimer,
    Slot,
)
from app.desktop_ui.tasks import BackgroundTask
from app.desktop_ui.theme import METRICS, build_desktop_stylesheet
from app.desktop_ui.transcription_controller import DesktopTranscriptionController
from app.desktop_ui.view import build_desktop_view
from schemas.runtime import PipelinePreparationResult
from schemas.transcription import TranscriptionRun
from services.bootstrap import AppContext, build_app_context


class VoiceDesktopWindow(QMainWindow):
    _NOTIFICATION_FRAMES = ("", ".", "..", "...")

    def __init__(self) -> None:
        super().__init__()
        self.context: AppContext | None = None
        self.current_audio_path: Path | None = None
        self.current_run_dir: Path | None = None
        self._record_finalize_path: Path | None = None
        self._record_finalize_size: int | None = None
        self._record_finalize_attempts = 0
        self.current_audio_stats: dict[str, str] = {}
        self.last_run: TranscriptionRun | None = None
        self.last_prepare_result: PipelinePreparationResult | None = None
        self._worker_thread: QThread | None = None
        self._worker: BackgroundTask | None = None
        self._worker_kind: str | None = None
        self._discard_worker_result = False
        self.input_devices: list[object] = []
        self._notification_reset_timer = QTimer(self)
        self._notification_reset_timer.setSingleShot(True)
        self._notification_reset_timer.timeout.connect(self._hide_notification)
        self._notification_animation_timer = QTimer(self)
        self._notification_animation_timer.setInterval(260)
        self._notification_animation_timer.timeout.connect(self._advance_notification_animation)
        self._notification_base_text = ""
        self._notification_animation_index = 0
        self._startup_message = "Loading local models from cache and initializing runtime"
        self._startup_thread: QThread | None = None
        self._startup_worker: BackgroundTask | None = None
        self._startup_ready = False
        self.capture_session: QMediaCaptureSession | None = None
        self.audio_input: QAudioInput | None = None
        self.recorder: QMediaRecorder | None = None
        self.player: QMediaPlayer | None = None
        self.audio_output: QAudioOutput | None = None
        self._audio_runtime_ready = False
        self.audio_controller = DesktopAudioController(self)
        self.transcription_controller = DesktopTranscriptionController(self)

        self.setWindowTitle("iVoice")
        self.resize(METRICS.window_width, METRICS.window_height)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setStyleSheet(build_desktop_stylesheet())
        self._bind_ui(build_desktop_view(self))
        QTimer.singleShot(0, self._initialize_window_state)

    def _initialize_window_state(self) -> None:
        self.audio_controller.populate_input_device_list(bind_device=False)
        self._set_play_button_visible(False)
        self._set_transcribe_button_mode(False)
        self._show_notification("Starting runtime", tone="warning", animate=True, auto_hide_ms=0)
        self._set_controls_enabled(False)
        self._refresh_details_panel()
        self._start_startup_bootstrap()

    def _bind_ui(self, ui) -> None:
        self.ui = ui
        self.root = ui.root
        self.notification_bar = ui.notification_bar
        self.notification_text = ui.notification_text
        self.notification_dismiss = ui.notification_dismiss
        self.details_button = ui.details_button
        self.language_input = ui.language_input
        self.input_device_combo = ui.input_device_combo
        self.record_button = ui.record_button
        self.play_button = ui.play_button
        self.open_button = ui.open_button
        self.transcribe_button = ui.transcribe_button
        self.audio_summary = ui.audio_summary
        self.transcript_box = ui.transcript_box
        self.copy_button = ui.copy_button
        self.details_dock = ui.details_dock
        self.details_box = ui.details_box

        self.play_button.setEnabled(False)
        self.transcribe_button.setEnabled(False)

        self.record_button.clicked.connect(self.audio_controller.toggle_recording)
        self.play_button.clicked.connect(self.audio_controller.play_audio)
        self.open_button.clicked.connect(self.audio_controller.open_wav)
        self.transcribe_button.clicked.connect(
            self.transcription_controller.transcribe_current_audio
        )
        self.input_device_combo.currentIndexChanged.connect(self.audio_controller.set_input_device)
        self.details_button.toggled.connect(self._toggle_details)
        self.copy_button.clicked.connect(self._copy_transcript)
        self.notification_dismiss.clicked.connect(self._hide_notification)
        self.details_dock.visibilityChanged.connect(self._sync_details_toggle)
        self._enable_button_tooltips()

    def _set_controls_enabled(self, enabled: bool) -> None:
        recorder_state = None
        if self.recorder is not None:
            recorder_state = self.recorder.recorderState()
        is_recording = recorder_state == QMediaRecorder.RecorderState.RecordingState
        self.record_button.setEnabled(enabled)
        self._set_record_button_mode(is_recording)
        self.open_button.setEnabled(enabled and not is_recording)
        has_audio = self.current_audio_path is not None and self._record_finalize_path is None
        self._set_play_button_visible(has_audio)
        self.play_button.setEnabled(enabled and has_audio and self.player is not None)
        self._set_transcribe_button_mode(self._worker_kind == "transcribe")
        transcribe_enabled = (enabled and has_audio) or self._worker_kind == "transcribe"
        self.transcribe_button.setEnabled(transcribe_enabled)
        self.input_device_combo.setEnabled(enabled and bool(self.input_devices))
        self.language_input.setEnabled(enabled)
        self.details_button.setEnabled(enabled)
        self.copy_button.setEnabled(enabled and bool(self.transcript_box.toPlainText().strip()))

    def _set_play_button_visible(self, visible: bool) -> None:
        self.play_button.setVisible(visible)

    def _set_play_button_mode(self, is_playing: bool) -> None:
        self.play_button.setProperty("active", is_playing)
        self.play_button.setText("⏸" if is_playing else "▶")
        self.play_button.setToolTip("Pause current audio" if is_playing else "Play current audio")
        self.play_button.style().unpolish(self.play_button)
        self.play_button.style().polish(self.play_button)

    def _set_record_button_mode(self, is_recording: bool) -> None:
        self.record_button.setProperty("active", is_recording)
        if is_recording:
            self.record_button.setText("Stop")
            self.record_button.setObjectName("dangerButton")
            self.record_button.setToolTip("Stop the current recording")
        else:
            self.record_button.setText("Record")
            self.record_button.setObjectName("recordButton")
            self.record_button.setToolTip("Record audio from the current input device")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)

    def _copy_transcript(self) -> None:
        text = self.transcript_box.toPlainText().strip()
        if not text:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self._show_notification("Copied", tone="success", auto_hide_ms=1200)

    def _set_transcribe_button_mode(self, is_running: bool) -> None:
        if is_running:
            self.transcribe_button.setText("Stop")
            self.transcribe_button.setObjectName("dangerButton")
            self.transcribe_button.setToolTip("Stop the current transcription task")
        else:
            self.transcribe_button.setText("Transcribe")
            self.transcribe_button.setObjectName("primaryButton")
            self.transcribe_button.setToolTip("Run local transcription for the current audio")
        self.transcribe_button.style().unpolish(self.transcribe_button)
        self.transcribe_button.style().polish(self.transcribe_button)

    def _enable_button_tooltips(self) -> None:
        always_show = Qt.WidgetAttribute.WA_AlwaysShowToolTips
        for widget in (
            self.notification_dismiss,
            self.details_button,
            self.record_button,
            self.play_button,
            self.open_button,
            self.transcribe_button,
            self.copy_button,
        ):
            widget.setAttribute(always_show, True)

    def _show_notification(
        self,
        text: str,
        *,
        tone: str = "warning",
        auto_hide_ms: int = 5000,
        animate: bool = False,
    ) -> None:
        self._notification_reset_timer.stop()
        self._notification_animation_timer.stop()
        self._notification_base_text = text
        self._notification_animation_index = 0
        self.notification_bar.setProperty("tone", tone)
        self.notification_bar.style().unpolish(self.notification_bar)
        self.notification_bar.style().polish(self.notification_bar)
        self.notification_bar.show()
        self.notification_bar.raise_()
        self._layout_notification_bar()
        if animate:
            self._advance_notification_animation()
            self._notification_animation_timer.start()
        else:
            self.notification_text.setText(text)
        if auto_hide_ms > 0:
            self._notification_reset_timer.start(auto_hide_ms)

    @Slot()
    def _advance_notification_animation(self) -> None:
        frame = self._NOTIFICATION_FRAMES[self._notification_animation_index]
        self.notification_text.setText(f"{self._notification_base_text}{frame}")
        self._notification_animation_index = (self._notification_animation_index + 1) % len(
            self._NOTIFICATION_FRAMES
        )

    @Slot()
    def _hide_notification(self) -> None:
        self._notification_reset_timer.stop()
        self._notification_animation_timer.stop()
        self.notification_bar.hide()

    def _layout_notification_bar(self) -> None:
        if not self.notification_bar.isVisible():
            return
        root_width = self.root.width()
        width = min(METRICS.notification_max_width, max(240, root_width - 48))
        x = (root_width - width) // 2
        y = METRICS.notification_overlay_top
        self.notification_bar.setGeometry(x, y, width, METRICS.notification_min_height)

    def _refresh_details_panel(self) -> None:
        details_text = build_details_text(
            context=self.context,
            input_devices=self.input_devices,
            current_device_index=self.input_device_combo.currentIndex(),
            current_audio_stats=self.current_audio_stats,
            last_prepare_result=self.last_prepare_result,
            last_run=self.last_run,
            startup_message=None if self._startup_ready else self._startup_message,
        )
        self.details_box.setPlainText(details_text)

    def _start_startup_bootstrap(self) -> None:
        thread = QThread(self)
        worker = BackgroundTask(self._bootstrap_context)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._handle_startup_success)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(self._handle_startup_failure)
        worker.failed.connect(thread.quit)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_startup_worker)

        self._startup_thread = thread
        self._startup_worker = worker
        thread.start()

    def _bootstrap_context(self) -> dict[str, object]:
        context = build_app_context()
        prepare_result = context.service.warm_up_pipeline()
        return {
            "context": context,
            "prepare": prepare_result.model_dump(mode="json"),
        }

    @Slot(object)
    def _handle_startup_success(self, result: object) -> None:
        payload = dict(result)
        self.context = payload["context"]
        self.last_prepare_result = PipelinePreparationResult.model_validate(payload["prepare"])
        self._startup_ready = True
        self.audio_controller.populate_input_device_list(bind_device=False)
        self._show_notification("Runtime ready", tone="success", auto_hide_ms=1800)
        self._set_controls_enabled(True)
        self._refresh_details_panel()

    @Slot(str)
    def _handle_startup_failure(self, message: str) -> None:
        self._startup_ready = False
        self._show_notification("Startup failed", tone="error", auto_hide_ms=0)
        self._startup_message = message
        self._refresh_details_panel()

    @Slot()
    def _clear_startup_worker(self) -> None:
        self._startup_thread = None
        self._startup_worker = None

    @Slot(bool)
    def _toggle_details(self, checked: bool) -> None:
        self.details_dock.setVisible(checked)

    @Slot(bool)
    def _sync_details_toggle(self, visible: bool) -> None:
        self.details_button.blockSignals(True)
        self.details_button.setChecked(visible)
        self.details_button.blockSignals(False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_notification_bar()
