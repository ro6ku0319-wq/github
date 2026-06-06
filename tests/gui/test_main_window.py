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
    assert window.navigation.item(3).text() == "节点审查"
    assert window.progress_bar.minimum() == 0
    assert window.progress_bar.maximum() == 100
    assert window.log_panel.toPlainText() == ""
    assert window.log_panel.isReadOnly()
    assert window.processing_panel.run_foundation.text() == "一键执行基础流程"
    assert window.processing_panel.run_node_analysis.text() == "分析候选节点"
    assert window.processing_panel.run_exports.text() == "导出 body cut"
    assert window.processing_panel.resolution_combo.currentData() == "portrait_1080p"
    assert window.processing_panel.resolution_combo.count() == 4
    assert window.thread_pool.maxThreadCount() >= 1

    window.close()
    app.processEvents()


def test_output_resolution_selection_is_saved_to_project_config(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)

    window.processing_panel.select_resolution("landscape_2k")
    app.processEvents()

    config = window._load_config()
    assert config["output_video"]["resolution_preset"] == "landscape_2k"
    assert config["output_video"]["width"] == 2560
    assert config["output_video"]["height"] == 1440
    assert "横屏 2K" in window.log_panel.toPlainText()
    window.close()
    app.processEvents()


def test_existing_custom_dimensions_select_matching_resolution_preset(
    tmp_path: Path,
) -> None:
    app = get_app()
    (tmp_path / "config.yaml").write_text(
        "output_video:\n  width: 1920\n  height: 1080\n",
        encoding="utf-8",
    )

    window = MainWindow(tmp_path)

    assert window.processing_panel.resolution_combo.currentData() == "landscape_1080p"
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


def test_run_node_analysis_ignores_repeat_click_while_worker_is_active(
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

    window._run_node_analysis()
    window._run_node_analysis()

    assert len(started_workers) == 1
    assert not window.processing_panel.run_foundation.isEnabled()
    assert not window.processing_panel.run_node_analysis.isEnabled()
    assert not window.processing_panel.run_exports.isEnabled()
    assert "任务正在运行" in window.log_panel.toPlainText()
    window._finish_worker(started_workers[0], "节点分析完成")
    assert window.processing_panel.run_foundation.isEnabled()
    assert window.processing_panel.run_node_analysis.isEnabled()
    assert window.processing_panel.run_exports.isEnabled()
    window.close()
    app.processEvents()


def test_run_exports_ignores_repeat_click_while_worker_is_active(
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

    window._run_exports()
    window._run_exports()

    assert len(started_workers) == 1
    assert not window.processing_panel.run_exports.isEnabled()
    assert "任务正在运行" in window.log_panel.toPlainText()
    window._finish_worker(started_workers[0], "导出完成")
    assert window.processing_panel.run_exports.isEnabled()
    window.close()
    app.processEvents()


def test_node_review_panel_loads_cut_decision_csv(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    csv_path = tmp_path / "output" / "cut_decision.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        "node_id,label,start_global_time,end_global_time\n"
        "node_0001,hair_detail,0.000,1.500\n",
        encoding="utf-8",
    )

    window._load_cut_decision()

    assert window.node_review_panel.table.rowCount() == 1
    assert window.node_review_panel.table.item(0, 0).text() == "node_0001"
    window.close()
    app.processEvents()


def test_node_review_panel_saves_edited_cut_decision_csv(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    csv_path = tmp_path / "output" / "cut_decision.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        "node_id,label,human_note\n"
        "node_0001,hair_detail,\n",
        encoding="utf-8",
    )

    window._load_cut_decision()
    window.node_review_panel.table.item(0, 2).setText("保留前发")
    window._save_cut_decision()

    assert "保留前发" in csv_path.read_text(encoding="utf-8")
    assert "已保存 cut_decision.csv" in window.log_panel.toPlainText()
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
