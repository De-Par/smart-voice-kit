from __future__ import annotations

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
    QPlainTextEdit = _QtPlaceholder  # type: ignore[assignment]
    QPushButton = _QtPlaceholder  # type: ignore[assignment]
    QSizePolicy = _QtPlaceholder  # type: ignore[assignment]
    QVBoxLayout = _QtPlaceholder  # type: ignore[assignment]
    QWidget = _QtPlaceholder  # type: ignore[assignment]
    PYSIDE_IMPORT_ERROR = error


__all__ = [
    "PYSIDE_IMPORT_ERROR",
    "QApplication",
    "QAudioInput",
    "QAudioOutput",
    "QComboBox",
    "QDockWidget",
    "QFileDialog",
    "QFrame",
    "QGridLayout",
    "QHBoxLayout",
    "QLabel",
    "QLineEdit",
    "QMainWindow",
    "QMediaCaptureSession",
    "QMediaDevices",
    "QMediaFormat",
    "QMediaPlayer",
    "QMediaRecorder",
    "QMessageBox",
    "QObject",
    "QPlainTextEdit",
    "QPushButton",
    "QSizePolicy",
    "QThread",
    "QTimer",
    "QUrl",
    "QVBoxLayout",
    "QWidget",
    "Qt",
    "Signal",
    "Slot",
]
