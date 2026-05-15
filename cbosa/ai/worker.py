"""
AIWorker — background QThread for AI operations.

Runs a zero-argument callable on a worker thread.
Emits result_ready(str) on success or error(str) if an exception is raised.
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QThread, pyqtSignal


class AIWorker(QThread):
    """Runs *fn* on a worker thread and emits the result or error."""

    result_ready = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, fn: Callable[[], object], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
            self.result_ready.emit(str(result))
        except Exception as exc:
            self.error.emit(str(exc))
