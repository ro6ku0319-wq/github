from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit


class LogPanel(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)

    def append_log(self, message: str) -> None:
        self.appendPlainText(message)
