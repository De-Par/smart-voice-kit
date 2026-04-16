from __future__ import annotations

from app.ui_desktop.qt import PYSIDE_IMPORT_ERROR, QApplication
from app.ui_desktop.window import VoiceDesktopWindow
from services.bootstrap import build_app_context


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
