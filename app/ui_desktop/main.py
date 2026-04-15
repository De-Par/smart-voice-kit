from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

try:  # pragma: no cover - import guard for optional runtime dependency
    from PySide6.QtCore import QObject, Qt, QThread, QTimer, QUrl, Signal, Slot
    from PySide6.QtMultimedia import (
        QAudioInput,
        QAudioOutput,
        QMediaCaptureSession,
        QMediaDevices,
        QMediaFormat,
        QMediaPlayer,
        QMediaRecorder,
    )
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QDockWidget,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QSizePolicy,
        QVBoxLayout,
        QWidget,
    )

    PYSIDE_IMPORT_ERROR = None
except ImportError as error:  # pragma: no cover - handled at runtime

    class _QtPlaceholder:
        def __init__(self, *args, **kwargs) -> None:
            pass

    def Signal(*args, **kwargs):  # type: ignore[misc]
        return None

    def Slot(*args, **kwargs):  # type: ignore[misc]
        def decorator(fn):
            return fn

        return decorator

    QObject = object  # type: ignore[assignment]
    QThread = _QtPlaceholder  # type: ignore[assignment]
    QTimer = _QtPlaceholder  # type: ignore[assignment]
    Qt = _QtPlaceholder  # type: ignore[assignment]
    QUrl = _QtPlaceholder  # type: ignore[assignment]
    QAudioInput = _QtPlaceholder  # type: ignore[assignment]
    QAudioOutput = _QtPlaceholder  # type: ignore[assignment]
    QMediaCaptureSession = _QtPlaceholder  # type: ignore[assignment]
    QMediaDevices = _QtPlaceholder  # type: ignore[assignment]
    QMediaFormat = _QtPlaceholder  # type: ignore[assignment]
    QMediaPlayer = _QtPlaceholder  # type: ignore[assignment]
    QMediaRecorder = _QtPlaceholder  # type: ignore[assignment]
    QApplication = _QtPlaceholder  # type: ignore[assignment]
    QComboBox = _QtPlaceholder  # type: ignore[assignment]
    QDockWidget = _QtPlaceholder  # type: ignore[assignment]
    QFileDialog = _QtPlaceholder  # type: ignore[assignment]
    QFrame = _QtPlaceholder  # type: ignore[assignment]
    QGridLayout = _QtPlaceholder  # type: ignore[assignment]
    QHBoxLayout = _QtPlaceholder  # type: ignore[assignment]
    QLabel = _QtPlaceholder  # type: ignore[assignment]
    QLineEdit = _QtPlaceholder  # type: ignore[assignment]
    QMainWindow = object  # type: ignore[assignment]
    QMessageBox = _QtPlaceholder  # type: ignore[assignment]
    QPushButton = _QtPlaceholder  # type: ignore[assignment]
    QPlainTextEdit = _QtPlaceholder  # type: ignore[assignment]
    QSizePolicy = _QtPlaceholder  # type: ignore[assignment]
    QVBoxLayout = _QtPlaceholder  # type: ignore[assignment]
    QWidget = _QtPlaceholder  # type: ignore[assignment]
    PYSIDE_IMPORT_ERROR = error

from core.audio import inspect_wav_bytes
from schemas.runtime import ASRPreparationResult
from schemas.transcription import TranscriptionRun
from services.bootstrap import AppContext, build_app_context

logger = logging.getLogger(__name__)


def _format_bytes(value: int) -> str:
    size = float(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{value} B"


def _format_dbfs(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} dBFS"


class BackgroundTask(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object]) -> None:
        super().__init__()
        self._fn = fn

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self._fn())
        except Exception as error:  # pragma: no cover - UI boundary
            logger.exception("Desktop background task failed")
            self.failed.emit(str(error))


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

        self.setWindowTitle("Smart Voice Kit")
        self.resize(1080, 660)
        self._apply_styles()
        self._build_ui()
        self._load_audio_inputs()
        self._bind_media_signals()
        self._set_play_button_visible(False)
        self._set_transcribe_button_mode(False)
        self._refresh_details_panel()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f3f5f7;
                color: #1f1f1f;
            }
            QWidget#appRoot {
                background: #f3f5f7;
            }
            QWidget#detailsRoot {
                background: #ffffff;
            }
            QLabel {
                background: transparent;
                color: #1f1f1f;
            }
            QLabel#titleLabel {
                font-size: 28px;
                font-weight: 700;
                color: #1f1f1f;
            }
            QLabel#subtitleLabel {
                color: #6b7280;
                font-size: 14px;
            }
            QFrame#notificationBar {
                background: #fff3d6;
                border: 1px solid #f5d47a;
                border-radius: 14px;
            }
            QFrame#notificationBar[variant="cold"] {
                background: #fff3d6;
                border: 1px solid #f5d47a;
            }
            QFrame#notificationBar[variant="download"] {
                background: #ffe6de;
                border: 1px solid #ffc4b2;
            }
            QLabel#notificationText {
                color: #7a5600;
                font-size: 13px;
                font-weight: 500;
            }
            QFrame#notificationBar[variant="download"] QLabel#notificationText {
                color: #9f2f12;
            }
            QPushButton#notificationDismiss {
                background: transparent;
                color: #7a5600;
                border: none;
                padding: 0;
                min-width: 18px;
                max-width: 18px;
                font-size: 14px;
                font-weight: 700;
            }
            QFrame#notificationBar[variant="download"] QPushButton#notificationDismiss {
                color: #9f2f12;
            }
            QLabel#statusBadge {
                border-radius: 16px;
                padding: 7px 14px;
                font-weight: 600;
            }
            QFrame#heroCard, QFrame#controlsCard, QFrame#transcriptCard {
                background: #ffffff;
                border: 1px solid #e6e9ef;
                border-radius: 24px;
            }
            QComboBox, QLineEdit, QPlainTextEdit {
                background: #ffffff;
                border: 1px solid #d9dee7;
                border-radius: 16px;
                padding: 12px 14px;
                selection-background-color: #fc5230;
                color: #1f1f1f;
            }
            QComboBox {
                padding-right: 28px;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #1f1f1f;
                border: 1px solid #d9dee7;
                border-radius: 14px;
                outline: 0;
                padding: 6px;
                selection-background-color: #eaf0f6;
                selection-color: #111827;
            }
            QComboBox QAbstractItemView::item {
                min-height: 30px;
                padding: 6px 10px;
                border-radius: 10px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #f4f7fb;
                color: #111827;
            }
            QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #fc5230;
            }
            QPushButton {
                background: #f4f6fa;
                color: #1f1f1f;
                border: 1px solid #e2e7ef;
                border-radius: 18px;
                padding: 11px 18px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #eceff4;
            }
            QPushButton:disabled {
                background: #f4f5f7;
                color: #a0a7b4;
                border: 1px solid #edf0f4;
            }
            QPushButton#primaryButton {
                background: #22c55e;
                color: white;
                border: 1px solid #22c55e;
            }
            QPushButton#primaryButton:hover {
                background: #16a34a;
                border: 1px solid #16a34a;
            }
            QPushButton#dangerButton {
                background: #fc5230;
                color: white;
                border: 1px solid #fc5230;
            }
            QPushButton#dangerButton:hover {
                background: #ec4828;
                border: 1px solid #ec4828;
            }
            QPushButton#playButton {
                background: #22c55e;
                color: white;
                border: 1px solid #22c55e;
                border-radius: 10px;
                padding: 0;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton#playButton:hover {
                background: #16a34a;
                border: 1px solid #16a34a;
            }
            QPushButton#playButton[active="true"] {
                background: #fc5230;
                border: 1px solid #fc5230;
            }
            QPushButton#playButton[active="true"]:hover {
                background: #ec4828;
                border: 1px solid #ec4828;
            }
            QPushButton#copyButton {
                background: #f4f6fa;
                color: #1f1f1f;
                border: 1px solid #e2e7ef;
                border-radius: 10px;
                padding: 0;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton#copyButton:hover {
                background: #eceff4;
                color: #1f1f1f;
                border: 1px solid #d7dee8;
            }
            QDockWidget {
                border: none;
            }
            QPlainTextEdit#detailsBox {
                background: #f7f9fc;
                border: 1px solid #e4e8f0;
                border-radius: 18px;
                padding: 14px;
                color: #2b313d;
            }
            """
        )

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("appRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        hero_card = QFrame()
        hero_card.setObjectName("heroCard")
        hero_layout = QVBoxLayout(hero_card)
        hero_layout.setContentsMargins(24, 24, 24, 24)
        hero_layout.setSpacing(10)

        title = QLabel("Smart Voice Kit")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Local recording, local playback, offline-first ASR.")
        subtitle.setObjectName("subtitleLabel")
        self.notification_bar = QFrame()
        self.notification_bar.setObjectName("notificationBar")
        notification_layout = QHBoxLayout(self.notification_bar)
        notification_layout.setContentsMargins(12, 10, 12, 10)
        notification_layout.setSpacing(10)
        self.notification_text = QLabel()
        self.notification_text.setObjectName("notificationText")
        self.notification_text.setWordWrap(True)
        self.notification_dismiss = QPushButton("×")
        self.notification_dismiss.setObjectName("notificationDismiss")
        self.notification_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notification_dismiss.setToolTip("Dismiss")
        notification_layout.addWidget(self.notification_text, 1)
        notification_layout.addWidget(self.notification_dismiss)
        self.notification_bar.hide()

        header_row = QHBoxLayout()
        self.status_badge = QLabel("Ready")
        self.status_badge.setObjectName("statusBadge")
        self.details_button = QPushButton("Details")
        self.details_button.setCheckable(True)
        self.details_button.setChecked(False)
        self.details_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_row.addWidget(self.status_badge)
        header_row.addStretch(1)
        header_row.addWidget(self.details_button)

        hero_layout.addWidget(title)
        hero_layout.addWidget(subtitle)
        hero_layout.addWidget(self.notification_bar)
        hero_layout.addLayout(header_row)

        controls_card = QFrame()
        controls_card.setObjectName("controlsCard")
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(24, 22, 24, 22)
        controls_layout.setSpacing(16)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        self.language_input = QLineEdit()
        self.language_input.setPlaceholderText("Language (optional)")

        self.input_device_combo = QComboBox()
        self.record_button = QPushButton("Record")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("dangerButton")
        self.play_button = QPushButton("▶")
        self.play_button.setObjectName("playButton")
        self.play_button.setProperty("active", False)
        self.play_button.setToolTip("Play current audio")
        self.open_button = QPushButton("Open WAV")
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.setObjectName("primaryButton")

        grid.addWidget(QLabel("Input device"), 0, 0)
        grid.addWidget(self.input_device_combo, 0, 1)
        grid.addWidget(QLabel("Language"), 1, 0)
        grid.addWidget(self.language_input, 1, 1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        button_row.addWidget(self.record_button)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.open_button)
        button_row.addWidget(self.transcribe_button)

        self.audio_summary = QLabel("No audio selected.")
        self.audio_summary.setObjectName("subtitleLabel")
        summary_row = QHBoxLayout()
        summary_row.setSpacing(8)
        summary_row.addWidget(self.audio_summary)
        summary_row.addWidget(self.play_button)
        summary_row.addStretch(1)
        self.transcript_box = QPlainTextEdit()
        self.transcript_box.setPlaceholderText("Transcript will appear here.")
        self.transcript_box.setReadOnly(True)
        self.transcript_box.setMinimumHeight(0)
        self.transcript_box.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        transcript_card = QFrame()
        transcript_card.setObjectName("transcriptCard")
        transcript_card.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        transcript_layout = QVBoxLayout(transcript_card)
        transcript_layout.setContentsMargins(24, 20, 24, 20)
        transcript_layout.setSpacing(10)
        transcript_header = QHBoxLayout()
        transcript_header.setSpacing(6)
        transcript_title = QLabel("Transcript")
        transcript_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.copy_button = QPushButton("⎘")
        self.copy_button.setObjectName("copyButton")
        self.copy_button.setToolTip("Copy transcript to clipboard")
        self.copy_button.setEnabled(False)
        transcript_header.addWidget(transcript_title)
        transcript_header.addWidget(self.copy_button)
        transcript_header.addStretch(1)
        transcript_layout.addLayout(transcript_header)
        transcript_layout.addWidget(self.transcript_box)

        controls_layout.addLayout(grid)
        controls_layout.addLayout(button_row)
        controls_layout.addLayout(summary_row)

        layout.addWidget(hero_card)
        layout.addWidget(controls_card)
        layout.addWidget(transcript_card, 1)
        self.setCentralWidget(root)

        self._build_details_dock()

        self.stop_button.setEnabled(False)
        self.play_button.setEnabled(False)
        self.transcribe_button.setEnabled(False)

        self.record_button.clicked.connect(self.start_recording)
        self.stop_button.clicked.connect(self.stop_recording)
        self.play_button.clicked.connect(self.play_audio)
        self.open_button.clicked.connect(self.open_wav)
        self.transcribe_button.clicked.connect(self.transcribe_current_audio)
        self.input_device_combo.currentIndexChanged.connect(self._set_input_device)
        self.details_button.toggled.connect(self._toggle_details)
        self.notification_dismiss.clicked.connect(self._hide_notification)
        self.copy_button.clicked.connect(self._copy_transcript)

    def _build_details_dock(self) -> None:
        self.details_dock = QDockWidget("Details", self)
        self.details_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.details_dock.setFeatures(QDockWidget.DockWidgetClosable)
        self.details_dock.setMinimumWidth(320)

        details_root = QWidget()
        details_root.setObjectName("detailsRoot")
        details_layout = QVBoxLayout(details_root)
        details_layout.setContentsMargins(18, 18, 18, 18)
        details_layout.setSpacing(10)

        details_title = QLabel("Runtime Details")
        details_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        details_hint = QLabel("Optional technical details about the model and current audio.")
        details_hint.setObjectName("subtitleLabel")

        self.details_box = QPlainTextEdit()
        self.details_box.setObjectName("detailsBox")
        self.details_box.setReadOnly(True)
        self.details_box.setMinimumWidth(320)

        details_layout.addWidget(details_title)
        details_layout.addWidget(details_hint)
        details_layout.addWidget(self.details_box, 1)
        self.details_dock.setWidget(details_root)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.details_dock)
        self.details_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.details_dock.setTitleBarWidget(QWidget())
        self.details_dock.hide()
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
        self.record_button.setEnabled(not is_recording)
        self.stop_button.setEnabled(is_recording)
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
        self._set_play_button_visible(True)
        self.transcribe_button.setEnabled(True)

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
        if getattr(self.context.service.asr_engine, "_model", None) is None:
            self._show_notification(
                "Cold start: initializing local ASR. This may take a bit.",
                variant="cold",
            )
        else:
            self._hide_notification()
        self._run_background(
            fn=lambda: self._transcribe_with_auto_prepare(audio_path, language),
            on_success=self._show_transcription_result,
            busy_message="Transcribing...",
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
    def _show_prepare_result(self, result: object) -> None:
        self.last_prepare_result = ASRPreparationResult.model_validate(result)
        self._set_status("Ready")
        self._refresh_details_panel()

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
                "Local ASR model prepared.",
                variant="download",
                auto_hide_ms=6500,
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
        self.record_button.setEnabled(enabled and not is_recording)
        self.stop_button.setEnabled(enabled and is_recording)
        self.open_button.setEnabled(enabled)
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
        if is_playing:
            self.play_button.setText("⏸")
        else:
            self.play_button.setText("▶")
        self.play_button.style().unpolish(self.play_button)
        self.play_button.style().polish(self.play_button)

    def _copy_transcript(self) -> None:
        text = self.transcript_box.toPlainText().strip()
        if not text:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

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
            auto_hide_ms=9000,
        )
        self._set_status("Stopping")

    def _show_notification(
        self,
        text: str,
        *,
        variant: str = "cold",
        auto_hide_ms: int = 9000,
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
            if "Local ASR model is not available" not in str(error):
                raise

        prepare_context = build_app_context(asr_local_files_only_override=False)
        prepare_result = prepare_context.service.prepare_asr()
        run = self.context.service.transcribe_file(audio_path, language=language)
        return {
            "run": run,
            "prepare": prepare_result,
        }

    def _set_status(self, text: str) -> None:
        self.status_badge.setText(text)
        normalized = text.lower()
        if "record" in normalized:
            style = "background: #ffe5de; color: #b8321b; border: 1px solid #ffd0c5;"
        elif "error" in normalized:
            style = "background: #ffe7e7; color: #b42318; border: 1px solid #ffd1d1;"
        elif "done" in normalized:
            style = "background: #dcfce7; color: #166534; border: 1px solid #bbf7d0;"
        elif "ready" in normalized:
            style = "background: #eef3ff; color: #3451a3; border: 1px solid #dbe5ff;"
        elif "stopp" in normalized:
            style = "background: #ffe6de; color: #9f2f12; border: 1px solid #ffc4b2;"
        else:
            style = "background: #eef3ff; color: #3451a3; border: 1px solid #dbe5ff;"
        self.status_badge.setStyleSheet(style)

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
            "size": _format_bytes(audio_path.stat().st_size),
            "duration": f"{stats.duration_seconds:.2f}s",
            "sample_rate": f"{stats.sample_rate} Hz",
            "channels": str(stats.channels),
            "sample_width": f"{stats.sample_width_bytes * 8}-bit",
            "peak": _format_dbfs(stats.peak_dbfs),
            "rms": _format_dbfs(stats.rms_dbfs),
            "silent": "yes" if stats.is_likely_silent else "no",
        }
        duration = self.current_audio_stats["duration"]
        sample_rate = self.current_audio_stats["sample_rate"]
        self.audio_summary.setText(f"{audio_path.name}  •  {duration}  •  {sample_rate}")
        self._refresh_details_panel()

    def _refresh_details_panel(self) -> None:
        sections: list[str] = []

        asr = self.context.settings.asr
        sections.append(
            "\n".join(
                [
                    "[Model]",
                    f"backend: {self.context.service.asr_engine.backend_name}",
                    f"model: {self.context.service.asr_engine.model_name}",
                    f"device: {asr.device}",
                    f"compute_type: {asr.compute_type}",
                    f"offline_only: {asr.local_files_only}",
                    f"download_root: {asr.download_root}",
                ]
            )
        )

        device_text = "<none>"
        if getattr(self, "input_devices", None):
            current_index = self.input_device_combo.currentIndex()
            if 0 <= current_index < len(self.input_devices):
                device_text = self.input_devices[current_index].description()
        sections.append("[Audio Input]\n" + f"device: {device_text}")

        if self.current_audio_stats:
            sections.append(
                "[Current Audio]\n"
                + "\n".join(f"{key}: {value}" for key, value in self.current_audio_stats.items())
            )

        if self.last_prepare_result is not None:
            downloaded_files = (
                f"{self.last_prepare_result.downloaded_files}/"
                f"{self.last_prepare_result.total_files}"
            )
            downloaded_bytes = _format_bytes(self.last_prepare_result.downloaded_bytes)
            total_bytes = _format_bytes(self.last_prepare_result.total_bytes)
            sections.append(
                "[Last Prepare]\n"
                + "\n".join(
                    [
                        f"mode: {self.last_prepare_result.mode}",
                        f"downloaded_files: {downloaded_files}",
                        f"downloaded_bytes: {downloaded_bytes}",
                        f"total_bytes: {total_bytes}",
                    ]
                )
            )

        if self.last_run is not None:
            metadata = self.last_run.metadata
            sections.append(
                "[Last Run]\n"
                + "\n".join(
                    [
                        f"run_id: {metadata.id}",
                        f"language: {metadata.language or '<unknown>'}",
                        f"inference: {metadata.inference_seconds:.2f}s",
                        f"audio_path: {metadata.audio_path}",
                    ]
                )
            )

        self.details_box.setPlainText("\n\n".join(sections))

    @Slot(bool)
    def _toggle_details(self, checked: bool) -> None:
        self.details_dock.setVisible(checked)

    @Slot(bool)
    def _sync_details_toggle(self, visible: bool) -> None:
        self.details_button.blockSignals(True)
        self.details_button.setChecked(visible)
        self.details_button.blockSignals(False)


def run() -> None:
    if PYSIDE_IMPORT_ERROR is not None:
        raise SystemExit(
            "PySide6 is not installed in the current environment. "
            "Install project dependencies first: `pip install -e .`."
        ) from PYSIDE_IMPORT_ERROR

    app = QApplication.instance() or QApplication([])
    context = build_app_context()
    window = VoiceDesktopWindow(context)
    window.show()
    app.exec()


if __name__ == "__main__":
    run()
