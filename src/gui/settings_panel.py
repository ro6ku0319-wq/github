from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


def _double(minimum: float, maximum: float, decimals: int = 2) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setDecimals(decimals)
    return widget


class SettingsPanel(QWidget):
    save_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.acceleration_spin = _double(1.0, 100.0, 2)
        self.width_spin = QSpinBox()
        self.height_spin = QSpinBox()
        for widget in (self.width_spin, self.height_spin):
            widget.setRange(16, 16384)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 240)
        self.crop_mode_combo = QComboBox()
        self.crop_mode_combo.addItems(["center", "fit", "custom"])
        self.custom_crop_x_spin = QSpinBox()
        self.custom_crop_y_spin = QSpinBox()
        self.custom_crop_w_spin = QSpinBox()
        self.custom_crop_h_spin = QSpinBox()
        for widget in (
            self.custom_crop_x_spin,
            self.custom_crop_y_spin,
            self.custom_crop_w_spin,
            self.custom_crop_h_spin,
        ):
            widget.setRange(0, 16384)
        self.coarse_interval_spin = _double(0.05, 30.0, 3)
        self.fine_every_spin = QSpinBox()
        self.fine_every_spin.setRange(1, 120)
        self.boundary_window_spin = _double(0.05, 30.0, 3)
        self.completion_frames_spin = QSpinBox()
        self.completion_frames_spin.setRange(1, 300)
        self.min_duration_spin = _double(0.05, 120.0, 3)
        self.body_45_spin = QSpinBox()
        self.body_60_spin = QSpinBox()
        self.body_120_spin = QSpinBox()
        for widget in (self.body_45_spin, self.body_60_spin, self.body_120_spin):
            widget.setRange(1, 3600)
        rows = [
            ("加速倍数", self.acceleration_spin),
            ("输出宽度", self.width_spin),
            ("输出高度", self.height_spin),
            ("输出 FPS", self.fps_spin),
            ("裁剪模式", self.crop_mode_combo),
            ("自定义裁剪 X", self.custom_crop_x_spin),
            ("自定义裁剪 Y", self.custom_crop_y_spin),
            ("自定义裁剪宽度", self.custom_crop_w_spin),
            ("自定义裁剪高度", self.custom_crop_h_spin),
            ("粗采样间隔（秒）", self.coarse_interval_spin),
            ("精采样每 N 帧", self.fine_every_spin),
            ("边界搜索窗口（秒）", self.boundary_window_spin),
            ("完成保持帧数", self.completion_frames_spin),
            ("最短节点（秒）", self.min_duration_spin),
            ("45 秒版目标时长", self.body_45_spin),
            ("60 秒版目标时长", self.body_60_spin),
            ("120 秒版目标时长", self.body_120_spin),
        ]
        for label, widget in rows:
            form.addRow(label, widget)
        layout.addLayout(form)
        self.priority_table = QTableWidget(0, 2)
        self.priority_table.setHorizontalHeaderLabels(["操作标签", "优先级"])
        layout.addWidget(self.priority_table)
        self.save_button = QPushButton("保存通用设置")
        layout.addWidget(self.save_button)
        layout.addStretch()
        self.save_button.clicked.connect(self.save_requested.emit)

    def load_config(self, config: dict[str, Any]) -> None:
        base = _section(config, "base_processing")
        video = _section(config, "output_video")
        fine = _section(config, "fine_cut")
        versions = _section(config, "cut_versions")
        priorities = _section(config, "operation_priority")
        self.acceleration_spin.setValue(float(base.get("acceleration_factor", 5.0)))
        self.width_spin.setValue(int(video.get("width", 1080)))
        self.height_spin.setValue(int(video.get("height", 1920)))
        self.fps_spin.setValue(int(video.get("fps", 30)))
        self.crop_mode_combo.setCurrentText(str(video.get("crop_mode", "center")))
        self.custom_crop_x_spin.setValue(int(video.get("custom_crop_x", 0)))
        self.custom_crop_y_spin.setValue(int(video.get("custom_crop_y", 0)))
        self.custom_crop_w_spin.setValue(int(video.get("custom_crop_w", 1080)))
        self.custom_crop_h_spin.setValue(int(video.get("custom_crop_h", 1920)))
        self.coarse_interval_spin.setValue(
            float(fine.get("coarse_sample_interval_seconds", 0.4))
        )
        self.fine_every_spin.setValue(int(fine.get("fine_sample_every_n_frames", 2)))
        self.boundary_window_spin.setValue(
            float(fine.get("boundary_search_window_seconds", 1.0))
        )
        self.completion_frames_spin.setValue(
            int(fine.get("completion_hold_frames", 3))
        )
        self.min_duration_spin.setValue(
            float(fine.get("min_node_duration_seconds", 0.25))
        )
        for name, widget, default in (
            ("body_45s", self.body_45_spin, 45),
            ("body_60s", self.body_60_spin, 60),
            ("body_120s", self.body_120_spin, 120),
        ):
            section = versions.get(name, {})
            value = section.get("target_duration_seconds", default) if isinstance(section, dict) else default
            widget.setValue(int(value))
        self.priority_table.setRowCount(len(priorities))
        for row, (label, priority) in enumerate(sorted(priorities.items())):
            label_item = QTableWidgetItem(str(label))
            label_item.setFlags(label_item.flags() & ~label_item.flags().ItemIsEditable)
            self.priority_table.setItem(row, 0, label_item)
            self.priority_table.setItem(row, 1, QTableWidgetItem(str(priority)))

    def config_values(self) -> dict[str, Any]:
        priorities: dict[str, int] = {}
        for row in range(self.priority_table.rowCount()):
            label_item = self.priority_table.item(row, 0)
            value_item = self.priority_table.item(row, 1)
            if label_item is None or value_item is None:
                continue
            try:
                priorities[label_item.text()] = int(value_item.text())
            except ValueError:
                priorities[label_item.text()] = 0
        return {
            "acceleration_factor": self.acceleration_spin.value(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "fps": self.fps_spin.value(),
            "crop_mode": self.crop_mode_combo.currentText(),
            "custom_crop_x": self.custom_crop_x_spin.value(),
            "custom_crop_y": self.custom_crop_y_spin.value(),
            "custom_crop_w": self.custom_crop_w_spin.value(),
            "custom_crop_h": self.custom_crop_h_spin.value(),
            "coarse_sample_interval_seconds": self.coarse_interval_spin.value(),
            "fine_sample_every_n_frames": self.fine_every_spin.value(),
            "boundary_search_window_seconds": self.boundary_window_spin.value(),
            "completion_hold_frames": self.completion_frames_spin.value(),
            "min_node_duration_seconds": self.min_duration_spin.value(),
            "body_45s": self.body_45_spin.value(),
            "body_60s": self.body_60_spin.value(),
            "body_120s": self.body_120_spin.value(),
            "operation_priority": priorities,
        }

    def set_actions_enabled(self, enabled: bool) -> None:
        self.save_button.setEnabled(enabled)
