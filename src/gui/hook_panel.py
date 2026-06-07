from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HookPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Blender Hook 由用户外部制作，不参与 ZBrush 节点分析"))
        self.enabled_checkbox = QCheckBox("启用 Blender Hook")
        self.concat_checkbox = QCheckBox("自动拼接 Hook 与 body cut")
        layout.addWidget(self.enabled_checkbox)
        layout.addWidget(self.concat_checkbox)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.choose_button = QPushButton("选择 Hook 视频")
        path_row.addWidget(self.path_edit)
        path_row.addWidget(self.choose_button)
        layout.addLayout(path_row)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("预期 Hook 时长（秒）"))
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 60.0)
        self.duration_spin.setDecimals(2)
        duration_row.addWidget(self.duration_spin)
        layout.addLayout(duration_row)

        self.save_button = QPushButton("保存 Hook 设置")
        self.export_button = QPushButton("自动拼接 Hook 与 body cut")
        layout.addWidget(self.save_button)
        layout.addWidget(self.export_button)
        layout.addStretch()
        self.choose_button.clicked.connect(self._choose_hook)

    def load_config(self, config: dict[str, Any]) -> None:
        self.enabled_checkbox.setChecked(bool(config.get("enabled", False)))
        self.concat_checkbox.setChecked(bool(config.get("concat_with_body_cut", True)))
        self.path_edit.setText(str(config.get("hook_video_path", "")))
        self.duration_spin.setValue(float(config.get("expected_duration_seconds", 2.0)))

    def config_values(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled_checkbox.isChecked(),
            "hook_video_path": self.path_edit.text().strip(),
            "concat_with_body_cut": self.concat_checkbox.isChecked(),
            "expected_duration_seconds": self.duration_spin.value(),
        }

    def set_actions_enabled(self, enabled: bool) -> None:
        self.save_button.setEnabled(enabled)
        self.export_button.setEnabled(enabled)
        self.choose_button.setEnabled(enabled)

    def _choose_hook(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "选择 Blender Hook 视频",
            str(Path(self.path_edit.text() or "input/hook")),
            "视频文件 (*.mp4 *.mov *.mkv)",
        )
        if selected:
            self.path_edit.setText(selected)
