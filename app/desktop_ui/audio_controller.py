from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.desktop_ui.qt import (
    QAudioInput,
    QAudioOutput,
    QFileDialog,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaFormat,
    QMediaPlayer,
    QMediaRecorder,
    QMessageBox,
    QTimer,
    QUrl,
    Slot,
)
from core.audio import inspect_wav_bytes
from core.formatting import format_bytes, format_dbfs

if TYPE_CHECKING:
    from app.desktop_ui.window import VoiceDesktopWindow

logger = logging.getLogger(__name__)


class DesktopAudioController:
    def __init__(self, window: VoiceDesktopWindow) -> None:
        self.window = window

    def populate_input_device_list(self, *, bind_device: bool) -> None:
        try:
            input_devices = list(QMediaDevices.audioInputs())
        except Exception:  # pragma: no cover - native multimedia boundary
            logger.exception("Failed to enumerate audio input devices")
            input_devices = []

        self.window.input_devices = input_devices
        self.window.input_device_combo.blockSignals(True)
        self.window.input_device_combo.clear()
        if input_devices:
            for device in input_devices:
                self.window.input_device_combo.addItem(device.description())
            self.window.input_device_combo.setCurrentIndex(0)
        else:
            self.window.input_device_combo.addItem("No input devices detected")
            self.window.input_device_combo.setCurrentIndex(0)
        self.window.input_device_combo.blockSignals(False)
        self.window.input_device_combo.setEnabled(bool(input_devices))

        if bind_device and input_devices and self.window._audio_runtime_ready:
            self.set_input_device(self.window.input_device_combo.currentIndex())
        else:
            self.window._refresh_details_panel()

    def ensure_audio_runtime(self) -> bool:
        if self.window._audio_runtime_ready:
            return True

        try:
            self.window.capture_session = QMediaCaptureSession(self.window)
            self.window.audio_input = QAudioInput(self.window)
            self.window.capture_session.setAudioInput(self.window.audio_input)
            self.window.recorder = QMediaRecorder(self.window)
            self.window.capture_session.setRecorder(self.window.recorder)

            self.window.player = QMediaPlayer(self.window)
            self.window.audio_output = QAudioOutput(self.window)
            self.window.player.setAudioOutput(self.window.audio_output)
            self.window.audio_output.setVolume(1.0)
        except Exception as error:  # pragma: no cover - native multimedia boundary
            logger.exception("Failed to initialize desktop audio runtime")
            QMessageBox.critical(
                self.window,
                "Audio initialization failed",
                f"Desktop audio runtime could not be initialized: {error}",
            )
            return False

        self.window._audio_runtime_ready = True
        self.bind_media_signals()
        self.load_audio_inputs()
        return True

    def bind_media_signals(self) -> None:
        if self.window.recorder is None or self.window.player is None:
            return
        self.window.recorder.recorderStateChanged.connect(self.handle_recorder_state_changed)
        self.window.player.errorOccurred.connect(self.handle_player_error)
        self.window.player.playbackStateChanged.connect(self.handle_playback_state_changed)

    def load_audio_inputs(self) -> None:
        self.populate_input_device_list(bind_device=True)

    @Slot(int)
    def set_input_device(self, index: int) -> None:
        if not self.ensure_audio_runtime():
            return
        if not self.window.input_devices:
            return
        device = self.window.input_devices[index]
        if self.window.audio_input is None:
            return
        self.window.audio_input.setDevice(device)
        self.window._set_status("Ready")
        self.window._refresh_details_panel()

    @Slot(object)
    def handle_recorder_state_changed(self, state: object) -> None:
        is_recording = state == QMediaRecorder.RecorderState.RecordingState
        self.window._set_record_button_mode(is_recording)
        has_audio = self.window.current_audio_path is not None
        is_finalizing = self.window._record_finalize_path is not None
        self.window.play_button.setEnabled(has_audio and not is_recording and not is_finalizing)
        self.window.transcribe_button.setEnabled(
            has_audio and not is_recording and not is_finalizing
        )
        if not is_recording and is_finalizing:
            QTimer.singleShot(220, self.finalize_recorded_audio)

    @Slot()
    def handle_player_error(self) -> None:
        if self.window.player.errorString():
            QMessageBox.warning(self.window, "Playback failed", self.window.player.errorString())

    @Slot(object)
    def handle_playback_state_changed(self, state: object) -> None:
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.window._set_play_button_mode(is_playing)

    @Slot()
    def toggle_recording(self) -> None:
        if not self.ensure_audio_runtime():
            return
        if self.window.recorder is None:
            return
        if self.window.recorder.recorderState() == QMediaRecorder.RecorderState.RecordingState:
            self.stop_recording()
            return
        self.start_recording()

    @Slot()
    def start_recording(self) -> None:
        if not self.ensure_audio_runtime():
            return
        if self.window.player is None or self.window.recorder is None:
            return
        if self.window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.window.player.stop()
        run_target = self.window.context.service.create_run_target()
        output_path = run_target.audio_path
        media_format = QMediaFormat(QMediaFormat.FileFormat.Wave)
        self.window.recorder.setMediaFormat(media_format)
        self.window.recorder.setOutputLocation(QUrl.fromLocalFile(str(output_path)))
        self.window.recorder.record()
        self.window.current_run_dir = run_target.run_dir
        self.window.current_audio_path = output_path
        self.window._record_finalize_path = None
        self.window._record_finalize_size = None
        self.window._record_finalize_attempts = 0
        self.window.current_audio_stats = {}
        self.window.audio_summary.setText("Recording...")
        self.window._set_status("Recording")
        self.window._set_play_button_visible(False)
        self.window.transcribe_button.setEnabled(False)
        self.window._refresh_details_panel()

    @Slot()
    def stop_recording(self) -> None:
        if self.window.recorder is None:
            return
        self.window.recorder.stop()
        if self.window.current_audio_path is not None:
            self.window._record_finalize_path = self.window.current_audio_path
            self.window._record_finalize_size = None
            self.window._record_finalize_attempts = 0
            self.window.audio_summary.setText("Finalizing recording...")
            self.window._set_status("Finalizing")
            self.window._set_play_button_visible(False)
            self.window.transcribe_button.setEnabled(False)

    @Slot()
    def play_audio(self) -> None:
        if not self.ensure_audio_runtime():
            return
        if self.window.player is None:
            return
        if self.window.current_audio_path is None or not self.window.current_audio_path.exists():
            QMessageBox.information(
                self.window,
                "No audio",
                "No local WAV recording is available yet.",
            )
            return
        if self.window.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.window.player.pause()
            return
        self.window.player.setSource(QUrl.fromLocalFile(str(self.window.current_audio_path)))
        self.window.player.play()

    @Slot()
    def open_wav(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Open WAV",
            str(Path.cwd()),
            "WAV files (*.wav)",
        )
        if not path:
            return

        self.window.current_audio_path = Path(path)
        self.window.current_run_dir = None
        self.window._record_finalize_path = None
        self.window._record_finalize_size = None
        self.window._record_finalize_attempts = 0
        self.update_audio_details(self.window.current_audio_path)
        self.window._set_status("Loaded")
        self.window._set_controls_enabled(True)

    def finalize_recorded_audio(self) -> None:
        audio_path = self.window._record_finalize_path
        if audio_path is None:
            return

        self.window._record_finalize_attempts += 1
        if not audio_path.exists():
            if self.window._record_finalize_attempts < 12:
                QTimer.singleShot(220, self.finalize_recorded_audio)
            return

        current_size = audio_path.stat().st_size
        if current_size <= 44 or self.window._record_finalize_size != current_size:
            self.window._record_finalize_size = current_size
            if self.window._record_finalize_attempts < 12:
                QTimer.singleShot(220, self.finalize_recorded_audio)
            return

        try:
            stats = inspect_wav_bytes(audio_path.read_bytes())
            if stats.duration_seconds <= 0 or stats.duration_seconds > 3600:
                raise ValueError(f"Suspicious recording duration: {stats.duration_seconds:.2f}s")
        except Exception:
            logger.exception("Recorded WAV is not finalized yet")
            if self.window._record_finalize_attempts < 12:
                QTimer.singleShot(220, self.finalize_recorded_audio)
            return

        self.window._record_finalize_path = None
        self.window._record_finalize_size = None
        self.window._record_finalize_attempts = 0
        self.update_audio_details(audio_path)
        self.window._set_status("Recorded")
        self.window._set_play_button_visible(True)
        self.window.play_button.setEnabled(True)
        self.window.transcribe_button.setEnabled(True)

    def update_audio_details(self, audio_path: Path) -> None:
        try:
            stats = inspect_wav_bytes(audio_path.read_bytes())
        except Exception as error:  # pragma: no cover - UI boundary
            logger.exception("Failed to inspect local audio")
            self.window.current_audio_stats = {
                "path": str(audio_path),
                "error": str(error),
            }
            self.window.audio_summary.setText(audio_path.name)
            self.window._refresh_details_panel()
            return

        self.window.current_audio_stats = {
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
        duration = self.window.current_audio_stats["duration"]
        sample_rate = self.window.current_audio_stats["sample_rate"]
        self.window.audio_summary.setText(f"{audio_path.name}  •  {duration}  •  {sample_rate}")
        self.window._refresh_details_panel()
