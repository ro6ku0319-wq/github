from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class ProjectSettingsPanel(QWidget):
    save_requested = Signal()
    reload_requested = Signal()
    open_project_requested = Signal()
    open_output_requested = Signal()
    project_directory_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.project_name_edit = QLineEdit()
        self.project_dir_label = QLabel()
        self.choose_project_button = QPushButton("选择项目目录")
        self.config_path_label = QLabel()
        self.input_dir_edit = QLineEdit()
        self.choose_input_button = QPushButton("选择素材目录")
        self.output_dir_edit = QLineEdit()
        self.choose_output_button = QPushButton("选择输出目录")
        form.addRow("项目名称", self.project_name_edit)
        project_row = QHBoxLayout()
        project_row.addWidget(self.project_dir_label)
        project_row.addWidget(self.choose_project_button)
        form.addRow("项目目录", project_row)
        form.addRow("配置文件", self.config_path_label)
        input_row = QHBoxLayout()
        input_row.addWidget(self.input_dir_edit)
        input_row.addWidget(self.choose_input_button)
        form.addRow("素材目录", input_row)
        output_row = QHBoxLayout()
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(self.choose_output_button)
        form.addRow("输出目录", output_row)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.save_button = QPushButton("保存项目设置")
        self.reload_button = QPushButton("重新加载配置")
        self.open_project_button = QPushButton("打开项目文件夹")
        self.open_output_button = QPushButton("打开输出文件夹")
        for button in (
            self.save_button,
            self.reload_button,
            self.open_project_button,
            self.open_output_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)
        layout.addStretch()
        self.save_button.clicked.connect(self.save_requested.emit)
        self.reload_button.clicked.connect(self.reload_requested.emit)
        self.open_project_button.clicked.connect(self.open_project_requested.emit)
        self.open_output_button.clicked.connect(self.open_output_requested.emit)
        self.choose_project_button.clicked.connect(self._choose_project)
        self.choose_input_button.clicked.connect(
            lambda: self._choose_configured_directory(self.input_dir_edit)
        )
        self.choose_output_button.clicked.connect(
            lambda: self._choose_configured_directory(self.output_dir_edit)
        )

    def load_config(self, project_dir: Path, config: dict[str, Any]) -> None:
        self.project_dir_label.setText(str(Path(project_dir).resolve()))
        self.config_path_label.setText(str(Path(project_dir).resolve() / "config.yaml"))
        self.project_name_edit.setText(str(_section(config, "project").get("name", "")))
        self.input_dir_edit.setText(str(_section(config, "input").get("input_dir", "input")))
        self.output_dir_edit.setText(
            str(_section(config, "output").get("output_dir", "output"))
        )

    def config_values(self) -> dict[str, str]:
        return {
            "project_name": self.project_name_edit.text().strip(),
            "input_dir": self.input_dir_edit.text().strip() or "input",
            "output_dir": self.output_dir_edit.text().strip() or "output",
        }

    def set_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.save_button,
            self.reload_button,
            self.choose_project_button,
            self.choose_input_button,
            self.choose_output_button,
        ):
            button.setEnabled(enabled)

    def _choose_project(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择项目目录",
            self.project_dir_label.text(),
        )
        if selected:
            self.project_directory_selected.emit(Path(selected))

    def _choose_configured_directory(self, target: QLineEdit) -> None:
        project_dir = Path(self.project_dir_label.text())
        current = Path(target.text().strip() or ".")
        start = current if current.is_absolute() else project_dir / current
        selected = QFileDialog.getExistingDirectory(self, "选择目录", str(start))
        if not selected:
            return
        path = Path(selected).resolve()
        try:
            target.setText(path.relative_to(project_dir.resolve()).as_posix())
        except ValueError:
            target.setText(str(path))
