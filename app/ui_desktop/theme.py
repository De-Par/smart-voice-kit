from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesktopPalette:
    background: str = "#f3f5f7"
    surface: str = "#ffffff"
    surface_muted: str = "#f7f9fc"
    text: str = "#1f1f1f"
    text_muted: str = "#6b7280"
    text_soft: str = "#2b313d"
    border: str = "#e6e9ef"
    border_soft: str = "#d9dee7"
    border_muted: str = "#e4e8f0"
    button_bg: str = "#f4f6fa"
    button_hover: str = "#eceff4"
    button_border: str = "#e2e7ef"
    button_hover_border: str = "#d7dee8"
    button_disabled_bg: str = "#f4f5f7"
    button_disabled_text: str = "#a0a7b4"
    button_disabled_border: str = "#edf0f4"
    selection: str = "#fc5230"
    selection_list: str = "#eaf0f6"
    selection_list_text: str = "#111827"
    primary: str = "#22c55e"
    primary_hover: str = "#16a34a"
    danger: str = "#fc5230"
    danger_hover: str = "#ec4828"
    notification_cold_bg: str = "#fff3d6"
    notification_cold_border: str = "#f5d47a"
    notification_cold_text: str = "#7a5600"
    notification_download_bg: str = "#ffe6de"
    notification_download_border: str = "#ffc4b2"
    notification_download_text: str = "#9f2f12"
    status_record_bg: str = "#ffe5de"
    status_record_border: str = "#ffd0c5"
    status_record_text: str = "#b8321b"
    status_error_bg: str = "#ffe7e7"
    status_error_border: str = "#ffd1d1"
    status_error_text: str = "#b42318"
    status_done_bg: str = "#dcfce7"
    status_done_border: str = "#bbf7d0"
    status_done_text: str = "#166534"
    status_ready_bg: str = "#eef3ff"
    status_ready_border: str = "#dbe5ff"
    status_ready_text: str = "#3451a3"


@dataclass(frozen=True)
class DesktopMetrics:
    window_width: int = 480
    window_height: int = 640
    root_margin_horizontal: int = 28
    root_margin_top: int = 24
    root_margin_bottom: int = 24
    root_spacing: int = 18
    hero_padding: int = 24
    hero_spacing: int = 10
    notification_padding_horizontal: int = 12
    notification_padding_vertical: int = 10
    notification_spacing: int = 10
    controls_padding_horizontal: int = 24
    controls_padding_top: int = 22
    controls_padding_bottom: int = 22
    controls_spacing: int = 16
    grid_spacing_horizontal: int = 12
    grid_spacing_vertical: int = 12
    button_row_spacing: int = 10
    summary_row_spacing: int = 8
    transcript_padding_horizontal: int = 24
    transcript_padding_top: int = 20
    transcript_padding_bottom: int = 20
    transcript_spacing: int = 10
    transcript_header_spacing: int = 6
    details_root_padding: int = 18
    details_root_spacing: int = 10
    card_radius: int = 24
    input_radius: int = 16
    input_padding_vertical: int = 12
    input_padding_horizontal: int = 14
    button_radius: int = 18
    button_padding_vertical: int = 11
    button_padding_horizontal: int = 18
    status_radius: int = 16
    status_padding_vertical: int = 7
    status_padding_horizontal: int = 14
    play_button_radius: int = 10
    play_button_size: int = 28
    notification_radius: int = 14
    details_min_width: int = 320
    section_title_size: int = 16
    title_size: int = 28
    subtitle_size: int = 14
    details_padding: int = 14


PALETTE = DesktopPalette()
METRICS = DesktopMetrics()


def build_desktop_stylesheet() -> str:
    p = PALETTE
    m = METRICS
    return f"""
        QMainWindow {{
            background: {p.background};
            color: {p.text};
        }}
        QWidget#appRoot {{
            background: {p.background};
        }}
        QWidget#detailsRoot {{
            background: {p.surface};
        }}
        QLabel {{
            background: transparent;
            color: {p.text};
        }}
        QLabel#titleLabel {{
            font-size: {m.title_size}px;
            font-weight: 700;
            color: {p.text};
        }}
        QLabel#subtitleLabel {{
            color: {p.text_muted};
            font-size: {m.subtitle_size}px;
        }}
        QLabel#sectionTitleLabel {{
            font-size: {m.section_title_size}px;
            font-weight: 700;
            color: {p.text};
        }}
        QFrame#notificationBar {{
            background: {p.notification_cold_bg};
            border: 1px solid {p.notification_cold_border};
            border-radius: {m.notification_radius}px;
        }}
        QFrame#notificationBar[variant="cold"] {{
            background: {p.notification_cold_bg};
            border: 1px solid {p.notification_cold_border};
        }}
        QFrame#notificationBar[variant="download"] {{
            background: {p.notification_download_bg};
            border: 1px solid {p.notification_download_border};
        }}
        QLabel#notificationText {{
            color: {p.notification_cold_text};
            font-size: 13px;
            font-weight: 500;
        }}
        QFrame#notificationBar[variant="download"] QLabel#notificationText {{
            color: {p.notification_download_text};
        }}
        QPushButton#notificationDismiss {{
            background: transparent;
            color: {p.notification_cold_text};
            border: none;
            padding: 0;
            min-width: 18px;
            max-width: 18px;
            font-size: 14px;
            font-weight: 700;
        }}
        QFrame#notificationBar[variant="download"] QPushButton#notificationDismiss {{
            color: {p.notification_download_text};
        }}
        QLabel#statusBadge {{
            border-radius: {m.status_radius}px;
            padding: {m.status_padding_vertical}px {m.status_padding_horizontal}px;
            font-weight: 600;
        }}
        QFrame#heroCard, QFrame#controlsCard, QFrame#transcriptCard {{
            background: {p.surface};
            border: 1px solid {p.border};
            border-radius: {m.card_radius}px;
        }}
        QComboBox, QLineEdit, QPlainTextEdit {{
            background: {p.surface};
            border: 1px solid {p.border_soft};
            border-radius: {m.input_radius}px;
            padding: {m.input_padding_vertical}px {m.input_padding_horizontal}px;
            selection-background-color: {p.selection};
            color: {p.text};
        }}
        QComboBox {{
            padding-right: 28px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 28px;
            margin-right: 8px;
        }}
        QComboBox QAbstractItemView {{
            background: {p.surface};
            color: {p.text};
            border: 1px solid {p.border_soft};
            border-radius: 14px;
            outline: 0;
            padding: 6px;
            selection-background-color: {p.selection_list};
            selection-color: {p.selection_list_text};
        }}
        QComboBox QAbstractItemView::item {{
            min-height: 30px;
            padding: 6px 10px;
            border-radius: 10px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background: {p.button_bg};
            color: {p.selection_list_text};
        }}
        QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {{
            border: 1px solid {p.selection};
        }}
        QPushButton {{
            background: {p.button_bg};
            color: {p.text};
            border: 1px solid {p.button_border};
            border-radius: {m.button_radius}px;
            padding: {m.button_padding_vertical}px {m.button_padding_horizontal}px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {p.button_hover};
        }}
        QPushButton:disabled {{
            background: {p.button_disabled_bg};
            color: {p.button_disabled_text};
            border: 1px solid {p.button_disabled_border};
        }}
        QPushButton#primaryButton {{
            background: {p.primary};
            color: white;
            border: 1px solid {p.primary};
        }}
        QPushButton#primaryButton:hover {{
            background: {p.primary_hover};
            border: 1px solid {p.primary_hover};
        }}
        QPushButton#dangerButton {{
            background: {p.danger};
            color: white;
            border: 1px solid {p.danger};
        }}
        QPushButton#dangerButton:hover {{
            background: {p.danger_hover};
            border: 1px solid {p.danger_hover};
        }}
        QPushButton#recordButton {{
            background: {p.button_bg};
            color: {p.text};
            border: 1px solid {p.button_border};
        }}
        QPushButton#recordButton:hover {{
            background: {p.button_hover};
            border: 1px solid {p.button_hover_border};
        }}
        QPushButton#playButton {{
            background: {p.primary};
            color: white;
            border: 1px solid {p.primary};
            border-radius: {m.play_button_radius}px;
            padding: 0;
            min-width: {m.play_button_size}px;
            max-width: {m.play_button_size}px;
            min-height: {m.play_button_size}px;
            max-height: {m.play_button_size}px;
            font-size: 12px;
            font-weight: 700;
        }}
        QPushButton#playButton:hover {{
            background: {p.primary_hover};
            border: 1px solid {p.primary_hover};
        }}
        QPushButton#playButton[active="true"] {{
            background: {p.danger};
            border: 1px solid {p.danger};
        }}
        QPushButton#playButton[active="true"]:hover {{
            background: {p.danger_hover};
            border: 1px solid {p.danger_hover};
        }}
        QPushButton#copyButton {{
            background: {p.button_bg};
            color: {p.text};
            border: 1px solid {p.button_border};
            border-radius: {m.play_button_radius}px;
            padding: 0;
            min-width: {m.play_button_size}px;
            max-width: {m.play_button_size}px;
            min-height: {m.play_button_size}px;
            max-height: {m.play_button_size}px;
            font-size: 13px;
            font-weight: 700;
        }}
        QPushButton#copyButton:hover {{
            background: {p.button_hover};
            color: {p.text};
            border: 1px solid {p.button_hover_border};
        }}
        QDockWidget {{
            border: none;
        }}
        QPlainTextEdit#detailsBox {{
            background: {p.surface_muted};
            border: 1px solid {p.border_muted};
            border-radius: {m.button_radius}px;
            padding: {m.details_padding}px;
            color: {p.text_soft};
        }}
    """


def status_badge_styles(text: str) -> str:
    normalized = text.lower()
    if "record" in normalized:
        return _status_style(
            PALETTE.status_record_bg, PALETTE.status_record_text, PALETTE.status_record_border
        )
    if "error" in normalized:
        return _status_style(
            PALETTE.status_error_bg, PALETTE.status_error_text, PALETTE.status_error_border
        )
    if "done" in normalized:
        return _status_style(
            PALETTE.status_done_bg, PALETTE.status_done_text, PALETTE.status_done_border
        )
    if "stopp" in normalized:
        return _status_style(
            PALETTE.notification_download_bg,
            PALETTE.notification_download_text,
            PALETTE.notification_download_border,
        )
    return _status_style(
        PALETTE.status_ready_bg, PALETTE.status_ready_text, PALETTE.status_ready_border
    )


def _status_style(background: str, text: str, border: str) -> str:
    return f"background: {background}; color: {text}; border: 1px solid {border};"
