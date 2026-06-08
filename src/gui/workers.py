from __future__ import annotations

from collections.abc import Callable
from time import perf_counter

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    log = Signal(str)
    progress = Signal(int, str)
    succeeded = Signal(str)
    failed = Signal(str)


class TaskWorker(QRunnable):
    def __init__(self, task: Callable[[WorkerSignals], None], name: str) -> None:
        super().__init__()
        self.task = task
        self.name = name
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        started = perf_counter()
        try:
            self.task(self.signals)
        except Exception as error:
            elapsed = perf_counter() - started
            self.signals.failed.emit(f"{self.name} 失败: {error}（耗时 {elapsed:.2f}s）")
            return
        elapsed = perf_counter() - started
        self.signals.succeeded.emit(f"{self.name} 完成（耗时 {elapsed:.2f}s）")
