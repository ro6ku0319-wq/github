from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LlmApplyPanel(QWidget):
    apply_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("应用外部 LLM 生成的 edit_decision.json"))
        row = QHBoxLayout()
        self.decision_path = QLineEdit("output/llm_result/edit_decision.json")
        self.choose_button = QPushButton("选择 JSON")
        row.addWidget(self.decision_path)
        row.addWidget(self.choose_button)
        layout.addLayout(row)
        self.apply_button = QPushButton("应用 LLM 剪辑说明书")
        layout.addWidget(self.apply_button)
        layout.addStretch()
        self.choose_button.clicked.connect(self._choose)
        self.apply_button.clicked.connect(
            lambda: self.apply_requested.emit(self.selected_decision_path())
        )

    def selected_decision_path(self) -> Path:
        return Path(self.decision_path.text().strip())

    def set_actions_enabled(self, enabled: bool) -> None:
        self.choose_button.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)

    def _choose(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "选择 edit_decision.json",
            self.decision_path.text(),
            "JSON 文件 (*.json)",
        )
        if selected:
            self.decision_path.setText(selected)
