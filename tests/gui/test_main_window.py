import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def get_app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_main_window_contains_navigation_progress_and_log_panel(
    tmp_path: Path,
) -> None:
    app = get_app()
    window = MainWindow(tmp_path)

    assert window.windowTitle() == "OB11 ZBrush Body Cut"
    assert window.navigation.count() >= 4
    assert window.navigation.item(0).text() == "项目设置"
    assert window.navigation.item(1).text() == "素材管理"
    assert window.navigation.item(2).text() == "基础处理"
    assert window.progress_bar.minimum() == 0
    assert window.progress_bar.maximum() == 100
    assert window.log_panel.toPlainText() == ""
    assert window.log_panel.isReadOnly()
    assert window.processing_panel.run_foundation.text() == "一键执行基础流程"
    assert window.thread_pool.maxThreadCount() >= 1

    window.close()
    app.processEvents()


def test_save_input_order_rejects_empty_table_without_writing_order_file(
    tmp_path: Path,
) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    order_file = tmp_path / "input" / "order.txt"

    window._save_input_order()

    assert not order_file.exists()
    assert "请先扫描素材" in window.log_panel.toPlainText()
    window.close()
    app.processEvents()


def test_run_foundation_ignores_repeat_click_while_worker_is_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    started_workers: list[object] = []

    class RecordingPool:
        def maxThreadCount(self) -> int:
            return 1

        def start(self, worker: object) -> None:
            started_workers.append(worker)

    monkeypatch.setattr(window, "thread_pool", RecordingPool())

    window._run_foundation()
    window._run_foundation()

    assert len(started_workers) == 1
    assert not window.processing_panel.run_foundation.isEnabled()
    assert "基础处理正在运行" in window.log_panel.toPlainText()
    window._finish_worker(started_workers[0], "基础处理完成")
    assert window.processing_panel.run_foundation.isEnabled()
    window.close()
    app.processEvents()


def test_input_panel_orders_files_and_moves_selected_rows(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    files = [tmp_path / "part1.mp4", tmp_path / "part2.mp4"]

    window.input_panel.set_files(files)
    assert window.input_panel.ordered_names() == ["part1.mp4", "part2.mp4"]

    window.input_panel.table.selectRow(1)
    window.input_panel.move_selected(-1)
    assert window.input_panel.ordered_names() == ["part2.mp4", "part1.mp4"]

    window.close()
    app.processEvents()
