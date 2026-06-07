from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


VIDEO_NAMES = [
    "auto_node_preview.mp4",
    "body_cut_45s.mp4",
    "body_cut_60s.mp4",
    "body_cut_120s.mp4",
    "llm_result/llm_guided_body_cut.mp4",
    "final_with_hook_45s.mp4",
    "final_with_hook_60s.mp4",
    "final_with_hook_120s.mp4",
]


class PreviewPanel(QWidget):
    refresh_requested = Signal()
    open_output_requested = Signal()
    open_path_requested = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        actions = QGridLayout()
        self.refresh_button = QPushButton("刷新预览")
        self.open_output_button = QPushButton("打开输出文件夹")
        actions.addWidget(self.refresh_button, 0, 0)
        actions.addWidget(self.open_output_button, 0, 1)
        self.video_buttons: dict[str, QPushButton] = {}
        for index, name in enumerate(VIDEO_NAMES, start=2):
            button = QPushButton(f"播放 {Path(name).name}")
            button.setEnabled(False)
            button.clicked.connect(
                lambda _checked=False, item=name: self.open_path_requested.emit(item)
            )
            self.video_buttons[name] = button
            actions.addWidget(button, index // 2, index % 2)
        layout.addLayout(actions)
        self.status_label = QLabel("尚未刷新预览")
        layout.addWidget(self.status_label)

        images = QWidget()
        image_layout = QGridLayout(images)
        self.image_labels: dict[str, QLabel] = {}
        for column, name in enumerate(("node_contact_sheet.jpg", "activity_curve.png")):
            label = QLabel(f"{name}: 未生成")
            label.setMinimumSize(320, 200)
            label.setScaledContents(False)
            self.image_labels[name] = label
            image_layout.addWidget(label, 0, column)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(images)
        layout.addWidget(scroll)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.open_output_button.clicked.connect(self.open_output_requested.emit)

    def refresh(self, output_dir: Path) -> None:
        output_dir = Path(output_dir)
        available: list[str] = []
        for name, button in self.video_buttons.items():
            exists = (output_dir / name).exists()
            button.setEnabled(exists)
            if exists:
                available.append(name)
        for name, label in self.image_labels.items():
            path = output_dir / name
            pixmap = QPixmap(str(path)) if path.exists() else QPixmap()
            if pixmap.isNull():
                label.setPixmap(QPixmap())
                label.setText(f"{name}: {'无法读取' if path.exists() else '未生成'}")
            else:
                label.setText("")
                label.setPixmap(
                    pixmap.scaled(
                        600,
                        500,
                        aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                        transformMode=Qt.TransformationMode.SmoothTransformation,
                    )
                )
                available.append(name)
        self.status_label.setText(
            "可用输出: " + (", ".join(available) if available else "无")
        )
