from __future__ import annotations

from dataclasses import dataclass

from app.desktop_ui.qt import (
    QComboBox,
    QDockWidget,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    Qt,
    QVBoxLayout,
    QWidget,
)
from app.desktop_ui.theme import METRICS


@dataclass(frozen=True)
class DesktopWidgets:
    root: QWidget
    notification_bar: QFrame
    notification_text: QLabel
    notification_dismiss: QPushButton
    details_button: QPushButton
    language_input: QLineEdit
    input_device_combo: QComboBox
    record_button: QPushButton
    play_button: QPushButton
    open_button: QPushButton
    transcribe_button: QPushButton
    audio_summary: QLabel
    transcript_box: QPlainTextEdit
    copy_button: QPushButton
    details_dock: QDockWidget
    details_box: QPlainTextEdit


def build_desktop_view(window) -> DesktopWidgets:
    m = METRICS
    root = QWidget(window)
    root.setObjectName("appRoot")
    layout = QVBoxLayout(root)
    layout.setContentsMargins(
        m.root_margin_horizontal,
        m.root_margin_top,
        m.root_margin_horizontal,
        m.root_margin_bottom,
    )
    layout.setSpacing(m.root_spacing)

    notification_bar = QFrame(root)
    notification_bar.setObjectName("notificationBar")
    notification_bar.hide()

    notification_layout = QHBoxLayout(notification_bar)
    notification_layout.setContentsMargins(
        m.notification_padding_horizontal,
        m.notification_padding_vertical,
        m.notification_padding_horizontal,
        m.notification_padding_vertical,
    )
    notification_layout.setSpacing(m.notification_spacing)

    notification_text = QLabel()
    notification_text.setObjectName("notificationText")
    notification_text.setWordWrap(False)
    notification_dismiss = QPushButton("×")
    notification_dismiss.setObjectName("notificationDismiss")
    notification_dismiss.setToolTip("Dismiss notification")
    notification_dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
    notification_dismiss.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    notification_layout.addWidget(notification_text, 1)
    notification_layout.addWidget(notification_dismiss)
    notification_bar.raise_()

    hero_card = QFrame()
    hero_card.setObjectName("heroCard")
    hero_layout = QVBoxLayout(hero_card)
    hero_layout.setContentsMargins(m.hero_padding, m.hero_padding, m.hero_padding, m.hero_padding)
    hero_layout.setSpacing(m.hero_spacing)

    header_row = QHBoxLayout()
    title = QLabel("iVoice")
    title.setObjectName("titleLabel")
    title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    details_button = QPushButton("Details")
    details_button.setCheckable(True)
    details_button.setChecked(False)
    details_button.setToolTip("Show runtime details")
    details_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    header_row.addWidget(title)
    header_row.addStretch(1)
    header_row.addWidget(details_button)

    hero_layout.addLayout(header_row)
    subtitle = QLabel("Instruction-driven speech starts with local capture and analysis.")
    subtitle.setObjectName("subtitleLabel")
    hero_layout.addWidget(subtitle)

    controls_card = QFrame()
    controls_card.setObjectName("controlsCard")
    controls_layout = QVBoxLayout(controls_card)
    controls_layout.setContentsMargins(
        m.controls_padding_horizontal,
        m.controls_padding_top,
        m.controls_padding_horizontal,
        m.controls_padding_bottom,
    )
    controls_layout.setSpacing(m.controls_spacing)

    grid = QGridLayout()
    grid.setHorizontalSpacing(m.grid_spacing_horizontal)
    grid.setVerticalSpacing(m.grid_spacing_vertical)
    grid.setColumnStretch(0, 0)
    grid.setColumnStretch(1, 1)

    language_input = QLineEdit()
    language_input.setPlaceholderText("Language hint (optional)")
    input_device_combo = QComboBox()
    record_button = QPushButton("Record")
    record_button.setObjectName("recordButton")
    record_button.setProperty("active", False)
    record_button.setToolTip("Record audio from the current input device")
    play_button = QPushButton("▶")
    play_button.setObjectName("playButton")
    play_button.setProperty("active", False)
    play_button.setToolTip("Play current audio")
    open_button = QPushButton("Open WAV")
    open_button.setToolTip("Open a local WAV file")
    transcribe_button = QPushButton("Transcribe")
    transcribe_button.setObjectName("primaryButton")
    transcribe_button.setToolTip("Run local transcription for the current audio")

    grid.addWidget(QLabel("Input device"), 0, 0)
    grid.addWidget(input_device_combo, 0, 1)
    grid.addWidget(QLabel("Language"), 1, 0)
    grid.addWidget(language_input, 1, 1)

    button_row = QHBoxLayout()
    button_row.setSpacing(m.button_row_spacing)
    button_row.addWidget(record_button)
    button_row.addWidget(open_button)
    button_row.addWidget(transcribe_button)

    audio_summary = QLabel("No audio selected.")
    audio_summary.setObjectName("subtitleLabel")
    summary_row = QHBoxLayout()
    summary_row.setSpacing(m.summary_row_spacing)
    summary_row.addWidget(audio_summary)
    summary_row.addWidget(play_button)
    summary_row.addStretch(1)

    transcript_box = QPlainTextEdit()
    transcript_box.setPlaceholderText("Transcript will appear here.")
    transcript_box.setReadOnly(True)
    transcript_box.setMinimumHeight(0)
    transcript_box.setSizePolicy(
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
    transcript_layout.setContentsMargins(
        m.transcript_padding_horizontal,
        m.transcript_padding_top,
        m.transcript_padding_horizontal,
        m.transcript_padding_bottom,
    )
    transcript_layout.setSpacing(m.transcript_spacing)
    transcript_header = QHBoxLayout()
    transcript_header.setSpacing(m.transcript_header_spacing)

    transcript_title = QLabel("Transcript")
    transcript_title.setObjectName("sectionTitleLabel")
    copy_button = QPushButton("⎘")
    copy_button.setObjectName("copyButton")
    copy_button.setToolTip("Copy transcript to clipboard")
    copy_button.setEnabled(False)
    transcript_header.addWidget(transcript_title)
    transcript_header.addWidget(copy_button)
    transcript_header.addStretch(1)
    transcript_layout.addLayout(transcript_header)
    transcript_layout.addWidget(transcript_box)

    controls_layout.addLayout(grid)
    controls_layout.addLayout(button_row)
    controls_layout.addLayout(summary_row)

    layout.addWidget(hero_card)
    layout.addWidget(controls_card)
    layout.addWidget(transcript_card, 1)
    window.setCentralWidget(root)

    details_dock, details_box = _build_details_dock(window)

    return DesktopWidgets(
        root=root,
        notification_bar=notification_bar,
        notification_text=notification_text,
        notification_dismiss=notification_dismiss,
        details_button=details_button,
        language_input=language_input,
        input_device_combo=input_device_combo,
        record_button=record_button,
        play_button=play_button,
        open_button=open_button,
        transcribe_button=transcribe_button,
        audio_summary=audio_summary,
        transcript_box=transcript_box,
        copy_button=copy_button,
        details_dock=details_dock,
        details_box=details_box,
    )


def _build_details_dock(window) -> tuple[QDockWidget, QPlainTextEdit]:
    m = METRICS
    details_dock = QDockWidget("Details", window)
    details_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
    details_dock.setFeatures(QDockWidget.DockWidgetClosable)
    details_dock.setMinimumWidth(m.details_min_width)

    details_root = QWidget()
    details_root.setObjectName("detailsRoot")
    details_layout = QVBoxLayout(details_root)
    details_layout.setContentsMargins(
        m.details_root_padding,
        m.details_root_padding,
        m.details_root_padding,
        m.details_root_padding,
    )
    details_layout.setSpacing(m.details_root_spacing)

    details_title = QLabel("Runtime Details")
    details_title.setObjectName("sectionTitleLabel")

    details_box = QPlainTextEdit()
    details_box.setObjectName("detailsBox")
    details_box.setReadOnly(True)
    details_box.setMinimumWidth(m.details_min_width)

    details_layout.addWidget(details_title, alignment=Qt.AlignCenter)
    details_layout.addWidget(details_box, 1)
    details_dock.setWidget(details_root)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, details_dock)
    details_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
    details_dock.setTitleBarWidget(QWidget())
    details_dock.hide()

    return details_dock, details_box
