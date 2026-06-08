from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.llm_decision_editor import (
    EDITABLE_FIELDS,
    editable_rows_from_payload,
    payload_from_editable_rows,
    read_decision_payload,
    write_decision_payload,
)


class LlmApplyPanel(QWidget):
    apply_requested = Signal(object)
    save_requested = Signal()
    confirm_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.headers = list(EDITABLE_FIELDS)
        self.payload: dict | None = None
        self.loaded_path: Path | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("应用外部 LLM 生成的 edit_decision.json"))
        row = QHBoxLayout()
        self.decision_path = QLineEdit("output/llm_result/edit_decision.json")
        self.choose_button = QPushButton("选择 JSON")
        row.addWidget(self.decision_path)
        row.addWidget(self.choose_button)
        layout.addLayout(row)
        self.table = QTableWidget(0, len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        layout.addWidget(self.table)
        button_row = QHBoxLayout()
        self.load_button = QPushButton("加载 JSON")
        self.save_button = QPushButton("保存 JSON")
        self.apply_button = QPushButton("应用生成视频")
        self.confirm_button = QPushButton("确认最终方案并学习")
        for button in (
            self.load_button,
            self.save_button,
            self.apply_button,
            self.confirm_button,
        ):
            button_row.addWidget(button)
        layout.addLayout(button_row)
        layout.addStretch()
        self.choose_button.clicked.connect(self._choose)
        self.load_button.clicked.connect(lambda: self.load_json(self.selected_decision_path()))
        self.save_button.clicked.connect(self.save_json)
        self.apply_button.clicked.connect(
            lambda: self.apply_requested.emit(self.selected_decision_path())
        )
        self.save_button.clicked.connect(self.save_requested.emit)
        self.confirm_button.clicked.connect(self.confirm_requested.emit)

    def selected_decision_path(self) -> Path:
        return Path(self.decision_path.text().strip())

    def load_json(self, path: Path) -> None:
        self.loaded_path = Path(path)
        self.decision_path.setText(str(path))
        self.payload = read_decision_payload(self.loaded_path)
        rows = editable_rows_from_payload(self.payload)
        self.table.setRowCount(len(rows))
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        for row_index, row in enumerate(rows):
            for column_index, field in enumerate(self.headers):
                self.table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(str(row.get(field, ""))),
                )

    def save_json(self) -> None:
        if self.payload is None:
            self.load_json(self.selected_decision_path())
        assert self.payload is not None
        path = self.loaded_path or self.selected_decision_path()
        rows: list[dict[str, str]] = []
        for row_index in range(self.table.rowCount()):
            rows.append(
                {
                    field: self.table.item(row_index, column_index).text()
                    if self.table.item(row_index, column_index) is not None
                    else ""
                    for column_index, field in enumerate(self.headers)
                }
            )
        self.payload = payload_from_editable_rows(self.payload, rows)
        write_decision_payload(path, self.payload)

    def set_actions_enabled(self, enabled: bool) -> None:
        self.choose_button.setEnabled(enabled)
        self.load_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.apply_button.setEnabled(enabled)
        self.confirm_button.setEnabled(enabled)

    def _choose(self) -> None:
        selected, _filter = QFileDialog.getOpenFileName(
            self,
            "选择 edit_decision.json",
            self.decision_path.text(),
            "JSON 文件 (*.json)",
        )
        if selected:
            self.decision_path.setText(selected)
