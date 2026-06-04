from __future__ import annotations

from collections.abc import Callable

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
        try:
            self.task(self.signals)
        except Exception as error:
            self.signals.failed.emit(f"{self.name} 失败: {error}")
            return
        self.signals.succeeded.emit(f"{self.name} 完成")
