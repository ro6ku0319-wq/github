from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
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
        self.phase_balance_checkbox = QCheckBox("生成 JSON 前约束大型/细化比例")
        self.phase_balance_checkbox.setChecked(True)
        layout.addWidget(self.phase_balance_checkbox)
        ratio_row = QHBoxLayout()
        ratio_row.addWidget(QLabel("大型"))
        self.blockout_ratio_spin = QDoubleSpinBox()
        self.blockout_ratio_spin.setRange(0.1, 20.0)
        self.blockout_ratio_spin.setDecimals(2)
        self.blockout_ratio_spin.setSingleStep(0.1)
        self.blockout_ratio_spin.setValue(1.0)
        ratio_row.addWidget(self.blockout_ratio_spin)
        ratio_row.addWidget(QLabel("细化"))
        self.refinement_ratio_spin = QDoubleSpinBox()
        self.refinement_ratio_spin.setRange(0.1, 20.0)
        self.refinement_ratio_spin.setDecimals(2)
        self.refinement_ratio_spin.setSingleStep(0.1)
        self.refinement_ratio_spin.setValue(2.0)
        ratio_row.addWidget(self.refinement_ratio_spin)
        layout.addLayout(ratio_row)
        self.build_package_button = QPushButton("生成 LLM 视觉证据包")
        layout.addWidget(self.build_package_button)
        self.codex_generate_button = QPushButton("Codex 一键生成剪辑说明书")
        layout.addWidget(self.codex_generate_button)

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
        self.phase_balance_checkbox.toggled.connect(self._set_phase_ratio_enabled)
        self._set_phase_ratio_enabled(self.phase_balance_checkbox.isChecked())

    def selected_decision_path(self) -> Path:
        return Path(self.decision_path.text().strip())

    def load_config(self, config: dict[str, Any]) -> None:
        llm_package = config.get("llm_package", {})
        if not isinstance(llm_package, dict):
            llm_package = {}
        self.phase_balance_checkbox.setChecked(
            bool(llm_package.get("phase_balance_enabled", True))
        )
        self.blockout_ratio_spin.setValue(
            float(llm_package.get("blockout_duration_weight", 1.0))
        )
        self.refinement_ratio_spin.setValue(
            float(llm_package.get("refinement_duration_weight", 2.0))
        )
        self._set_phase_ratio_enabled(self.phase_balance_checkbox.isChecked())

    def config_values(self) -> dict[str, float | bool]:
        return {
            "phase_balance_enabled": self.phase_balance_checkbox.isChecked(),
            "blockout_duration_weight": self.blockout_ratio_spin.value(),
            "refinement_duration_weight": self.refinement_ratio_spin.value(),
        }

    def set_actions_enabled(self, enabled: bool) -> None:
        self.build_package_button.setEnabled(enabled)
        self.codex_generate_button.setEnabled(enabled)
        self.apply_decision_button.setEnabled(enabled)
        self.choose_decision_button.setEnabled(enabled)
        self.phase_balance_checkbox.setEnabled(enabled)
        self._set_phase_ratio_enabled(enabled and self.phase_balance_checkbox.isChecked())

    def _choose_decision(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "选择 edit_decision.json",
            self.decision_path.text(),
            "JSON 文件 (*.json)",
        )
        if selected:
            self.decision_path.setText(selected)

    def _set_phase_ratio_enabled(self, enabled: bool) -> None:
        self.blockout_ratio_spin.setEnabled(enabled)
        self.refinement_ratio_spin.setEnabled(enabled)
