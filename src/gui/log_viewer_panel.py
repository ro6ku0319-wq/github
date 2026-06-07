from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget


class LogViewerPanel(QWidget):
    refresh_requested = Signal()
    open_logs_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        self.refresh_button = QPushButton("刷新日志")
        self.open_logs_button = QPushButton("打开日志文件夹")
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.open_logs_button)
        layout.addLayout(actions)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.open_logs_button.clicked.connect(self.open_logs_requested.emit)

    def refresh(self, logs_dir: Path) -> None:
        files = sorted(Path(logs_dir).glob("bodycut-*.log"), reverse=True)
        if not files:
            self.text.setPlainText("尚未生成日志")
            return
        chunks: list[str] = []
        for path in files[:5]:
            chunks.extend([f"===== {path.name} =====", path.read_text(encoding="utf-8")])
        self.text.setPlainText("\n".join(chunks))
