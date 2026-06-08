from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class InputPanel(QWidget):
    scan_requested = Signal()
    save_order_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("素材管理"))

        actions = QHBoxLayout()
        self.scan_button = QPushButton("扫描 input 文件夹")
        self.move_up_button = QPushButton("上移")
        self.move_down_button = QPushButton("下移")
        self.save_order_button = QPushButton("保存 order.txt")
        actions.addWidget(self.scan_button)
        actions.addWidget(self.move_up_button)
        actions.addWidget(self.move_down_button)
        actions.addWidget(self.save_order_button)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文件名", "路径", "顺序"])
        layout.addWidget(self.table)

        self.scan_button.clicked.connect(self.scan_requested.emit)
        self.save_order_button.clicked.connect(self.save_order_requested.emit)
        self.move_up_button.clicked.connect(lambda: self.move_selected(-1))
        self.move_down_button.clicked.connect(lambda: self.move_selected(1))

    def set_files(self, paths: list[Path]) -> None:
        self.table.setRowCount(len(paths))
        for row, path in enumerate(paths):
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem(str(path)))
            self.table.setItem(row, 2, QTableWidgetItem(str(row + 1)))
        if paths:
            self.table.selectRow(0)

    def ordered_names(self) -> list[str]:
        return [
            self.table.item(row, 0).text()
            for row in range(self.table.rowCount())
            if self.table.item(row, 0) is not None
        ]

    def move_selected(self, offset: int) -> None:
        row = self.table.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.table.rowCount():
            return

        current_values = self._row_values(row)
        target_values = self._row_values(target)
        self._set_row(row, target_values)
        self._set_row(target, current_values)
        self._renumber()
        self.table.selectRow(target)

    def _row_values(self, row: int) -> list[str]:
        return [
            self.table.item(row, column).text()
            for column in range(self.table.columnCount())
        ]

    def _set_row(self, row: int, values: list[str]) -> None:
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(value))

    def _renumber(self) -> None:
        for row in range(self.table.rowCount()):
            self.table.setItem(row, 2, QTableWidgetItem(str(row + 1)))
