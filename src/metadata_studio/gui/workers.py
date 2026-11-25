"""Background workers so the GUI never blocks the event loop."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core import service


class Worker(QObject):
    """Runs a single callable on a thread and reports progress/results."""

    progressed = Signal(int, int, object)   # done, total, FileReport
    finished = Signal(object)                # list[FileReport]
    error = Signal(str)

    def __init__(self, fn, files, **kw):
        super().__init__()
        self._fn = fn
        self._files = files
        self._kw = kw
        self._thread = None

    def run(self):
        try:
            results = service._run(
                self._files, lambda f: self._fn(f, **self._kw),
                self._kw.get("workers"), self._on_progress)
        except Exception as exc:  # pragma: no cover
            self.error.emit(str(exc))
            return
        self.finished.emit(results)

    def _on_progress(self, done, total, res):
        self.progressed.emit(done, total, res)

    def start(self):
        self._thread = QThread()
        self.moveToThread(self._thread)
        self._thread.started.connect(self.run)
        self._thread.start()
        return self._thread
