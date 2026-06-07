from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LlmWorkflowPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("手动 LLM 工作流（不会自动调用 OpenAI API）"))
        self.build_package_button = QPushButton("生成 LLM 视觉证据包")
        layout.addWidget(self.build_package_button)

        layout.addWidget(QLabel("edit_decision.json 路径"))
        path_row = QHBoxLayout()
        self.decision_path = QLineEdit("output/llm_result/edit_decision.json")
        self.choose_decision_button = QPushButton("选择 JSON")
        path_row.addWidget(self.decision_path)
        path_row.addWidget(self.choose_decision_button)
        layout.addLayout(path_row)
        self.apply_decision_button = QPushButton("应用 LLM 剪辑说明书")
        layout.addWidget(self.apply_decision_button)
        layout.addStretch()

        self.choose_decision_button.clicked.connect(self._choose_decision)

    def selected_decision_path(self) -> Path:
        return Path(self.decision_path.text().strip())

    def set_actions_enabled(self, enabled: bool) -> None:
        self.build_package_button.setEnabled(enabled)
        self.apply_decision_button.setEnabled(enabled)
        self.choose_decision_button.setEnabled(enabled)

    def _choose_decision(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "选择 edit_decision.json",
            self.decision_path.text(),
            "JSON 文件 (*.json)",
        )
        if selected:
            self.decision_path.setText(selected)
