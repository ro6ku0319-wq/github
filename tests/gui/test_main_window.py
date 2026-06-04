import os
from pathlib import Path

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
