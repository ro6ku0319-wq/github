from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QLabel, QPushButton, QVBoxLayout, QWidget

from src.core.output_resolution import RESOLUTION_PRESETS


class ProcessingPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("基础处理"))
        layout.addWidget(QLabel("输出分辨率（修改后需重新执行基础流程）"))
        self.resolution_combo = QComboBox()
        for preset in RESOLUTION_PRESETS.values():
            self.resolution_combo.addItem(preset.label, preset.key)
        layout.addWidget(self.resolution_combo)
        self.run_foundation = QPushButton("一键执行基础流程")
        self.run_node_analysis = QPushButton("分析候选节点")
        self.run_exports = QPushButton("导出 body cut")
        layout.addWidget(self.run_foundation)
        layout.addWidget(self.run_node_analysis)
        layout.addWidget(self.run_exports)
        layout.addStretch()

    def select_resolution(self, preset_key: str) -> None:
        index = self.resolution_combo.findData(preset_key)
        if index >= 0:
            self.resolution_combo.setCurrentIndex(index)
