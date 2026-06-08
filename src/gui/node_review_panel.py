from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:
        try:
            return float(self.text()) < float(other.text())
        except ValueError:
            return super().__lt__(other)


class NodeReviewPanel(QWidget):
    refresh_requested = Signal()
    save_requested = Signal()
    open_folder_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        self.refresh_button = QPushButton("刷新 cut_decision.csv")
        self.save_button = QPushButton("保存人工修改")
        self.open_folder_button = QPushButton("打开 CSV 文件夹")
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("筛选 node_id 或 label")
        self.keep_combo = QComboBox()
        self.keep_combo.addItems(["全部", "保留", "删除"])
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["按原顺序", "按置信度降序", "按时间升序"])
        for widget in (
            self.refresh_button,
            self.save_button,
            self.open_folder_button,
            self.filter_edit,
            self.keep_combo,
            self.sort_combo,
        ):
            actions.addWidget(widget)
        self.table = QTableWidget(0, 0)
        layout.addLayout(actions)
        layout.addWidget(self.table)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.save_button.clicked.connect(self.save_requested.emit)
        self.open_folder_button.clicked.connect(self.open_folder_requested.emit)
        self.filter_edit.textChanged.connect(self.apply_filters)
        self.keep_combo.currentTextChanged.connect(self.apply_filters)
        self.sort_combo.currentTextChanged.connect(self.apply_sort)

    def load_csv(self, path: Path) -> None:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
        self.table.setColumnCount(len(fieldnames))
        self.table.setHorizontalHeaderLabels(fieldnames)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, field in enumerate(fieldnames):
                value = row.get(field, "")
                item_type = (
                    NumericTableWidgetItem
                    if field in {"confidence", "start_global_time", "end_global_time"}
                    else QTableWidgetItem
                )
                self.table.setItem(
                    row_index,
                    column_index,
                    item_type(value),
                )
        self.apply_filters()
        self.apply_sort()

    def save_csv(self, path: Path) -> None:
        headers = self._headers()
        rows: list[dict[str, str]] = []
        for row in range(self.table.rowCount()):
            rows.append(
                {
                    header: self.table.item(row, column).text()
                    if self.table.item(row, column) is not None
                    else ""
                    for column, header in enumerate(headers)
                }
            )
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

    def apply_filters(self, *_args: object) -> None:
        headers = self._headers()
        label_column = headers.index("label") if "label" in headers else -1
        node_column = headers.index("node_id") if "node_id" in headers else -1
        keep_columns = [
            headers.index(name)
            for name in (
                "keep_in_body_45s",
                "keep_in_body_60s",
                "keep_in_body_120s",
            )
            if name in headers
        ]
        query = self.filter_edit.text().strip().lower()
        state = self.keep_combo.currentText()
        for row in range(self.table.rowCount()):
            text = " ".join(
                self.table.item(row, column).text().lower()
                for column in (node_column, label_column)
                if column >= 0 and self.table.item(row, column) is not None
            )
            kept = any(
                self.table.item(row, column) is not None
                and self.table.item(row, column).text().strip().lower()
                in {"true", "1", "yes"}
                for column in keep_columns
            )
            visible = not query or query in text
            if state == "保留":
                visible = visible and kept
            elif state == "删除":
                visible = visible and not kept
            self.table.setRowHidden(row, not visible)

    def apply_sort(self, *_args: object) -> None:
        headers = self._headers()
        choice = self.sort_combo.currentText()
        if choice == "按置信度降序" and "confidence" in headers:
            self.table.sortItems(
                headers.index("confidence"),
                Qt.SortOrder.DescendingOrder,
            )
        elif choice == "按时间升序" and "start_global_time" in headers:
            self.table.sortItems(
                headers.index("start_global_time"),
                Qt.SortOrder.AscendingOrder,
            )

    def _headers(self) -> list[str]:
        return [
            self.table.horizontalHeaderItem(column).text()
            for column in range(self.table.columnCount())
            if self.table.horizontalHeaderItem(column) is not None
        ]
