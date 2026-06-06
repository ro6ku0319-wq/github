from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class NodeReviewPanel(QWidget):
    refresh_requested = Signal()
    save_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        self.refresh_button = QPushButton("刷新 cut_decision.csv")
        self.save_button = QPushButton("保存人工修改")
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.save_button)
        self.table = QTableWidget(0, 0)
        layout.addLayout(actions)
        layout.addWidget(self.table)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.save_button.clicked.connect(self.save_requested.emit)

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
                self.table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(row.get(field, "")),
                )

    def save_csv(self, path: Path) -> None:
        headers = [
            self.table.horizontalHeaderItem(column).text()
            for column in range(self.table.columnCount())
            if self.table.horizontalHeaderItem(column) is not None
        ]
        rows: list[dict[str, str]] = []
        for row in range(self.table.rowCount()):
            values: dict[str, str] = {}
            for column, header in enumerate(headers):
                item = self.table.item(row, column)
                values[header] = item.text() if item is not None else ""
            rows.append(values)

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
