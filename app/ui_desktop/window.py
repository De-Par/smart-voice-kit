from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from app.ui_desktop.helpers import build_details_text, format_bytes, format_dbfs
from app.ui_desktop.qt import (
    QApplication,
    QAudioInput,
    QAudioOutput,
    QFileDialog,
    QMainWindow,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaPlayer,
    QMediaRecorder,
    QMessageBox,
    QThread,
    QTimer,
    QUrl,
    Slot,
)
from app.ui_desktop.tasks import BackgroundTask
from app.ui_desktop.theme import METRICS, build_desktop_stylesheet, status_badge_styles
from app.ui_desktop.view import build_desktop_view
from core.audio import inspect_wav_bytes
from schemas.runtime import ASRPreparationResult
from schemas.transcription import TranscriptionRun
from services.asr_assets import FasterWhisperAssetPreparer
from services.bootstrap import AppContext

logger = logging.getLogger(__name__)


class VoiceDesktopWindow(QMainWindow):
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.current_audio_path: Path | None = None
        self._record_finalize_path: Path | None = None
        self._record_finalize_size: int | None = None
        self._record_finalize_attempts = 0
        self.current_audio_stats: dict[str, str] = {}
        self.last_run: TranscriptionRun | None = None
        self.last_prepare_result: ASRPreparationResult | None = None
        self._worker_thread: QThread | None = None
        self._worker: BackgroundTask | None = None
        self._worker_kind: str | None = None
        self._discard_worker_result = False
        self.input_devices: list[object] = []
        self._notification_timer = QTimer(self)
        self._notification_timer.setSingleShot(True)
        self._notification_timer.timeout.connect(self._hide_notification)

        self.capture_session = QMediaCaptureSession(self)
        self.audio_input = QAudioInput(self)
        self.capture_session.setAudioInput(self.audio_input)
        self.recorder = QMediaRecorder(self)
        self.capture_session.setRecorder(self.recorder)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(1.0)

        self.setWindowTitle("iVoice")
        self.resize(METRICS.window_width, METRICS.window_height)
        self.setStyleSheet(build_desktop_stylesheet())
        self._bind_ui(build_desktop_view(self))
        self._load_audio_inputs()
        self._bind_media_signals()
        self._set_play_button_visible(False)
        self._set_transcribe_button_mode(False)
        self._refresh_details_panel()

    def _bind_ui(self, ui) -> None:
        self.ui = ui
        self.notification_bar = ui.notification_bar
        self.notification_text = ui.notification_text
        self.notification_dismiss = ui.notification_dismiss
        self.status_badge = ui.status_badge
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

        self.record_button.clicked.connect(self.toggle_recording)
        self.play_button.clicked.connect(self.play_audio)
        self.open_button.clicked.connect(self.open_wav)
        self.transcribe_button.clicked.connect(self.transcribe_current_audio)
        self.input_device_combo.currentIndexChanged.connect(self._set_input_device)
        self.details_button.toggled.connect(self._toggle_details)
        self.notification_dismiss.clicked.connect(self._hide_notification)
        self.copy_button.clicked.connect(self._copy_transcript)
        self.details_dock.visibilityChanged.connect(self._sync_details_toggle)

    def _bind_media_signals(self) -> None:
        self.recorder.recorderStateChanged.connect(self._handle_recorder_state_changed)
        self.player.errorOccurred.connect(self._handle_player_error)
        self.player.playbackStateChanged.connect(self._handle_playback_state_changed)

    def _load_audio_inputs(self) -> None:
        self.input_devices = list(QMediaDevices.audioInputs())
        self.input_device_combo.clear()
        for device in self.input_devices:
            self.input_device_combo.addItem(device.description())
        if self.input_devices:
            self._set_input_device(0)

    @Slot(int)
    def _set_input_device(self, index: int) -> None:
        if not self.input_devices:
            return
        device = self.input_devices[index]
        self.audio_input.setDevice(device)
        self._set_status("Ready")
        self._refresh_details_panel()

    @Slot(object)
    def _handle_recorder_state_changed(self, state: object) -> None:
        is_recording = state == QMediaRecorder.RecorderState.RecordingState
        self._set_record_button_mode(is_recording)
        has_audio = self.current_audio_path is not None
        is_finalizing = self._record_finalize_path is not None
        self.play_button.setEnabled(has_audio and not is_recording and not is_finalizing)
        self.transcribe_button.setEnabled(has_audio and not is_recording and not is_finalizing)
        if not is_recording and is_finalizing:
            QTimer.singleShot(220, self._finalize_recorded_audio)

    @Slot()
    def _handle_player_error(self) -> None:
        if self.player.errorString():
            QMessageBox.warning(self, "Playback failed", self.player.errorString())

    @Slot(object)
    def _handle_playback_state_changed(self, state: object) -> None:
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._set_play_button_mode(is_playing)

    @Slot()
    def toggle_recording(self) -> None:
        if self.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.stop_recording()
            return
        self.start_recording()

    def _next_capture_path(self) -> Path:
        capture_dir = self.context.settings.storage.data_dir / "captures"
        capture_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return capture_dir / f"capture_{timestamp}.wav"

    @Slot()
    def start_recording(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        output_path = self._next_capture_path()
        media_format = QMediaFormat(QMediaFormat.FileFormat.Wave)
        self.recorder.setMediaFormat(media_format)
        self.recorder.setOutputLocation(QUrl.fromLocalFile(str(output_path)))
        self.recorder.record()
        self.current_audio_path = output_path
        self._record_finalize_path = None
        self._record_finalize_size = None
        self._record_finalize_attempts = 0
        self.current_audio_stats = {}
        self.audio_summary.setText("Recording...")
        self._set_status("Recording")
        self._set_play_button_visible(False)
        self.transcribe_button.setEnabled(False)
        self._refresh_details_panel()

    @Slot()
    def stop_recording(self) -> None:
        self.recorder.stop()
        if self.current_audio_path is not None:
            self._record_finalize_path = self.current_audio_path
            self._record_finalize_size = None
            self._record_finalize_attempts = 0
            self.audio_summary.setText("Finalizing recording...")
            self._set_status("Finalizing")
            self._set_play_button_visible(False)
            self.transcribe_button.setEnabled(False)

    @Slot()
    def play_audio(self) -> None:
        if self.current_audio_path is None or not self.current_audio_path.exists():
            QMessageBox.information(self, "No audio", "No local WAV recording is available yet.")
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            return
        self.player.setSource(QUrl.fromLocalFile(str(self.current_audio_path)))
        self.player.play()

    @Slot()
    def open_wav(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open WAV",
            str(Path.cwd()),
            "WAV files (*.wav)",
        )
        if not path:
            return
        
        self.current_audio_path = Path(path)
        self._record_finalize_path = None
        self._record_finalize_size = None
        self._record_finalize_attempts = 0
        self._update_audio_details(self.current_audio_path)
        self._set_status("Loaded")
        self._set_controls_enabled(True)

    @Slot()
    def transcribe_current_audio(self) -> None:
        if self._worker_kind == "transcribe":
            self._request_stop_transcription()
            return
        if self.current_audio_path is None or not self.current_audio_path.exists():
            QMessageBox.information(self, "No audio", "Record or open a WAV file first.")
            return
        if self._record_finalize_path is not None:
            QMessageBox.information(
                self,
                "Audio is not ready",
                "The recording is still being finalized. Please wait a moment.",
            )
            return

        language = self.language_input.text().strip() or None
        audio_path = self.current_audio_path
        cold_start = getattr(self.context.service.asr_engine, "_model", None) is None
        if cold_start:
            self._show_notification(
                "Cold start: checking model cache and preparing local speech analysis. "
                "The first run may take a while.",
                variant="cold",
                auto_hide_ms=0,
            )
        else:
            self._hide_notification()
        self._run_background(
            fn=lambda: self._transcribe_with_auto_prepare(audio_path, language),
            on_success=self._show_transcription_result,
            busy_message="Cold start..." if cold_start else "Transcribing...",
            kind="transcribe",
        )

    def _run_background(
        self,
        fn: Callable[[], object],
        on_success: Callable[[object], None],
        busy_message: str,
        kind: str | None = None,
    ) -> None:
        if self._worker_thread is not None:
            QMessageBox.information(self, "Busy", "Another operation is already running.")
            return

        self._worker_kind = kind
        self._discard_worker_result = False
        self._set_status(busy_message)
        self._set_controls_enabled(False)

        thread = QThread(self)
        worker = BackgroundTask(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_success)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(self._show_error)
        worker.failed.connect(thread.quit)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_worker)

        self._worker_thread = thread
        self._worker = worker
        thread.start()

    @Slot(object)
    def _show_transcription_result(self, result: object) -> None:
        prepare_payload = None
        if isinstance(result, dict):
            prepare_payload = result.get("prepare")
            if prepare_payload is not None:
                self.last_prepare_result = ASRPreparationResult.model_validate(prepare_payload)
            result = result["run"]

        if self._discard_worker_result:
            self._discard_worker_result = False
            self._hide_notification()
            self._set_status("Ready")
            self._refresh_details_panel()
            return

        self.last_run = TranscriptionRun.model_validate(result)
        self.transcript_box.setPlainText(self.last_run.metadata.transcript)
        self.copy_button.setEnabled(bool(self.last_run.metadata.transcript.strip()))
        if prepare_payload is not None:
            self._show_notification(
                "Local speech model prepared.",
                variant="download",
                auto_hide_ms=5000,
            )
        else:
            self._hide_notification()
        self._set_status("Done")
        self._refresh_details_panel()

    @Slot(str)
    def _show_error(self, message: str) -> None:
        self._hide_notification()
        self._set_status("Error")
        QMessageBox.critical(self, "Operation failed", message)

    @Slot()
    def _clear_worker(self) -> None:
        self._worker_thread = None
        self._worker = None
        self._worker_kind = None
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        recorder_state = self.recorder.recorderState()
        is_recording = recorder_state == QMediaRecorder.RecorderState.RecordingState
        self.record_button.setEnabled(enabled)
        self._set_record_button_mode(is_recording)
        self.open_button.setEnabled(enabled and not is_recording)
        has_audio = self.current_audio_path is not None and self._record_finalize_path is None
        self._set_play_button_visible(has_audio)
        self.play_button.setEnabled(enabled and has_audio)
        self._set_transcribe_button_mode(self._worker_kind == "transcribe")
        transcribe_enabled = (enabled and has_audio) or self._worker_kind == "transcribe"
        self.transcribe_button.setEnabled(transcribe_enabled)
        self.input_device_combo.setEnabled(enabled)
        self.language_input.setEnabled(enabled)

    def _set_play_button_visible(self, visible: bool) -> None:
        self.play_button.setVisible(visible)

    def _set_play_button_mode(self, is_playing: bool) -> None:
        self.play_button.setProperty("active", is_playing)
        self.play_button.setText("⏸" if is_playing else "▶")
        self.play_button.style().unpolish(self.play_button)
        self.play_button.style().polish(self.play_button)

    def _set_record_button_mode(self, is_recording: bool) -> None:
        self.record_button.setProperty("active", is_recording)
        if is_recording:
            self.record_button.setText("Stop")
            self.record_button.setObjectName("dangerButton")
        else:
            self.record_button.setText("Record")
            self.record_button.setObjectName("recordButton")
        self.record_button.style().unpolish(self.record_button)
        self.record_button.style().polish(self.record_button)

    def _copy_transcript(self) -> None:
        text = self.transcript_box.toPlainText().strip()
        if not text:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self._show_notification("Transcript copied.", variant="cold", auto_hide_ms=1500)

    def _set_transcribe_button_mode(self, is_running: bool) -> None:
        if is_running:
            self.transcribe_button.setText("Stop")
            self.transcribe_button.setObjectName("dangerButton")
        else:
            self.transcribe_button.setText("Transcribe")
            self.transcribe_button.setObjectName("primaryButton")
        self.transcribe_button.style().unpolish(self.transcribe_button)
        self.transcribe_button.style().polish(self.transcribe_button)

    def _request_stop_transcription(self) -> None:
        self._discard_worker_result = True
        self.transcribe_button.setEnabled(False)
        self._show_notification(
            "Stop requested. Waiting for the current step to finish.",
            variant="download",
            auto_hide_ms=5000,
        )
        self._set_status("Stopping")

    def _show_notification(
        self,
        text: str,
        *,
        variant: str = "cold",
        auto_hide_ms: int = 5000,
    ) -> None:
        self._notification_timer.stop()
        self.notification_text.setText(text)
        self.notification_bar.setProperty("variant", variant)
        self.notification_bar.style().unpolish(self.notification_bar)
        self.notification_bar.style().polish(self.notification_bar)
        self.notification_bar.show()
        if auto_hide_ms > 0:
            self._notification_timer.start(auto_hide_ms)

    def _hide_notification(self) -> None:
        self._notification_timer.stop()
        self.notification_bar.hide()

    def _transcribe_with_auto_prepare(
        self,
        audio_path: Path,
        language: str | None,
    ) -> dict[str, object]:
        try:
            run = self.context.service.transcribe_file(audio_path, language=language)
            return {"run": run}
        except RuntimeError as error:
            if "Local speech model is not available" not in str(error):
                raise

        prepare_result = FasterWhisperAssetPreparer(self.context.settings.asr).prepare()
        run = self.context.service.transcribe_file(audio_path, language=language)
        return {
            "run": run,
            "prepare": prepare_result,
        }

    def _set_status(self, text: str) -> None:
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(status_badge_styles(text))

    def _finalize_recorded_audio(self) -> None:
        audio_path = self._record_finalize_path
        if audio_path is None:
            return

        self._record_finalize_attempts += 1
        if not audio_path.exists():
            if self._record_finalize_attempts < 12:
                QTimer.singleShot(220, self._finalize_recorded_audio)
            return

        current_size = audio_path.stat().st_size
        if current_size <= 44 or self._record_finalize_size != current_size:
            self._record_finalize_size = current_size
            if self._record_finalize_attempts < 12:
                QTimer.singleShot(220, self._finalize_recorded_audio)
            return

        try:
            stats = inspect_wav_bytes(audio_path.read_bytes())
            if stats.duration_seconds <= 0 or stats.duration_seconds > 3600:
                raise ValueError(f"Suspicious recording duration: {stats.duration_seconds:.2f}s")
        except Exception:
            logger.exception("Recorded WAV is not finalized yet")
            if self._record_finalize_attempts < 12:
                QTimer.singleShot(220, self._finalize_recorded_audio)
            return

        self._record_finalize_path = None
        self._record_finalize_size = None
        self._record_finalize_attempts = 0
        self._update_audio_details(audio_path)
        self._set_status("Recorded")
        self._set_play_button_visible(True)
        self.play_button.setEnabled(True)
        self.transcribe_button.setEnabled(True)

    def _update_audio_details(self, audio_path: Path) -> None:
        try:
            stats = inspect_wav_bytes(audio_path.read_bytes())
        except Exception as error:  # pragma: no cover - UI boundary
            logger.exception("Failed to inspect local audio")
            self.current_audio_stats = {
                "path": str(audio_path),
                "error": str(error),
            }
            self.audio_summary.setText(audio_path.name)
            self._refresh_details_panel()
            return

        self.current_audio_stats = {
            "path": str(audio_path),
            "size": format_bytes(audio_path.stat().st_size),
            "duration": f"{stats.duration_seconds:.2f}s",
            "sample_rate": f"{stats.sample_rate} Hz",
            "channels": str(stats.channels),
            "sample_width": f"{stats.sample_width_bytes * 8}-bit",
            "peak": format_dbfs(stats.peak_dbfs),
            "rms": format_dbfs(stats.rms_dbfs),
            "silent": "yes" if stats.is_likely_silent else "no",
        }
        duration = self.current_audio_stats["duration"]
        sample_rate = self.current_audio_stats["sample_rate"]
        self.audio_summary.setText(f"{audio_path.name}  •  {duration}  •  {sample_rate}")
        self._refresh_details_panel()

    def _refresh_details_panel(self) -> None:
        details_text = build_details_text(
            context=self.context,
            input_devices=self.input_devices,
            current_device_index=self.input_device_combo.currentIndex(),
            current_audio_stats=self.current_audio_stats,
            last_prepare_result=self.last_prepare_result,
            last_run=self.last_run,
        )
        self.details_box.setPlainText(details_text)

    @Slot(bool)
    def _toggle_details(self, checked: bool) -> None:
        self.details_dock.setVisible(checked)

    @Slot(bool)
    def _sync_details_toggle(self, visible: bool) -> None:
        self.details_button.blockSignals(True)
        self.details_button.setChecked(visible)
        self.details_button.blockSignals(False)
