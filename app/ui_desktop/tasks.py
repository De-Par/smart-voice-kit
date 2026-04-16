from __future__ import annotations

import logging
from collections.abc import Callable

from app.ui_desktop.qt import QObject, Signal, Slot

logger = logging.getLogger(__name__)


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
