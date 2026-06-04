from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class ProcessingPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("基础处理"))
        self.run_foundation = QPushButton("一键执行基础流程")
        layout.addWidget(self.run_foundation)
        layout.addStretch()
