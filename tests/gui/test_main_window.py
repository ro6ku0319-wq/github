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
    assert window.navigation.item(4).text() == "预览"
    assert window.navigation.item(5).text() == "LLM 证据包"
    assert window.navigation.item(6).text() == "应用 LLM 决策"
    assert window.navigation.item(7).text() == "Blender Hook"
    assert window.navigation.count() == 10
    assert window.preview_panel.refresh_button.text()
    assert window.project_settings_panel.save_button.text()
    assert window.settings_panel.save_button.text()
    assert window.log_viewer_panel.refresh_button.text()
    assert window.progress_bar.minimum() == 0
    assert window.progress_bar.maximum() == 100
    assert window.log_panel.toPlainText() == ""
    assert window.log_panel.isReadOnly()
    assert window.processing_panel.run_foundation.text() == "一键执行基础流程"
    assert window.processing_panel.run_node_analysis.text() == "分析候选节点"
    assert window.processing_panel.run_exports.text() == "导出 body cut"
    assert window.processing_panel.resolution_combo.currentData() == "portrait_1080p"
    assert window.processing_panel.resolution_combo.count() == 4
    assert window.llm_workflow_panel.build_package_button.text() == "生成 LLM 视觉证据包"
    assert window.llm_workflow_panel.apply_decision_button.text() == "应用 LLM 剪辑说明书"
    assert window.llm_workflow_panel.phase_balance_checkbox.text() == "生成 JSON 前约束大型/细化比例"
    assert window.hook_panel.export_button.text() == "自动拼接 Hook 与 body cut"
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


def test_hook_settings_are_saved_to_project_config(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)

    window.hook_panel.enabled_checkbox.setChecked(True)
    window.hook_panel.path_edit.setText("input/hook/intro.mp4")
    window.hook_panel.duration_spin.setValue(3.5)
    window._save_hook_settings()

    config = window._load_config()
    assert config["external_hook"]["enabled"] is True
    assert config["external_hook"]["hook_video_path"] == "input/hook/intro.mp4"
    assert config["external_hook"]["expected_duration_seconds"] == 3.5
    assert "已保存 Blender Hook 设置" in window.log_panel.toPlainText()
    window.close()
    app.processEvents()


def test_preview_panel_refreshes_available_images_and_videos(tmp_path: Path) -> None:
    app = get_app()
    output = tmp_path / "output"
    output.mkdir()
    (output / "node_contact_sheet.jpg").write_bytes(b"not-an-image")
    (output / "body_cut_60s.mp4").write_bytes(b"video")
    window = MainWindow(tmp_path)

    window._refresh_preview()

    assert window.preview_panel.video_buttons["body_cut_60s.mp4"].isEnabled()
    assert not window.preview_panel.video_buttons["body_cut_45s.mp4"].isEnabled()
    assert "body_cut_60s.mp4" in window.preview_panel.status_label.text()
    window.close()
    app.processEvents()


def test_preview_panel_refreshes_valid_images_without_qpixmap_keyword_error(
    tmp_path: Path,
) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    app = get_app()
    output = tmp_path / "output"
    output.mkdir()
    assert cv2.imwrite(
        str(output / "node_contact_sheet.jpg"),
        np.full((20, 30, 3), 128, dtype=np.uint8),
    )
    window = MainWindow(tmp_path)

    window._refresh_preview()

    assert "刷新预览失败" not in window.log_panel.toPlainText()
    assert window.preview_panel.image_labels["node_contact_sheet.jpg"].pixmap() is not None
    window.close()
    app.processEvents()


def test_general_settings_are_saved_to_project_config(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    window.settings_panel.acceleration_spin.setValue(12.0)
    window.settings_panel.width_spin.setValue(1440)
    window.settings_panel.height_spin.setValue(2560)
    window.settings_panel.fps_spin.setValue(60)
    window.settings_panel.crop_mode_combo.setCurrentText("custom")
    window.settings_panel.custom_crop_x_spin.setValue(10)
    window.settings_panel.custom_crop_y_spin.setValue(20)
    window.settings_panel.custom_crop_w_spin.setValue(1000)
    window.settings_panel.custom_crop_h_spin.setValue(1200)
    window.settings_panel.coarse_interval_spin.setValue(0.75)
    window.settings_panel.body_60_spin.setValue(75)
    window.settings_panel.priority_table.item(0, 1).setText("10")

    window._save_general_settings()

    config = window._load_config()
    assert config["base_processing"]["acceleration_factor"] == 12.0
    assert config["output_video"]["width"] == 1440
    assert config["output_video"]["height"] == 2560
    assert config["output_video"]["fps"] == 60
    assert config["output_video"]["crop_mode"] == "custom"
    assert config["output_video"]["custom_crop_x"] == 10
    assert config["output_video"]["custom_crop_y"] == 20
    assert config["output_video"]["custom_crop_w"] == 1000
    assert config["output_video"]["custom_crop_h"] == 1200
    assert config["fine_cut"]["coarse_sample_interval_seconds"] == 0.75
    assert config["cut_versions"]["body_60s"]["target_duration_seconds"] == 75
    first_label = window.settings_panel.priority_table.item(0, 0).text()
    assert config["operation_priority"][first_label] == 10
    window.close()
    app.processEvents()


def test_project_settings_save_name_and_directories(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    window.project_settings_panel.project_name_edit.setText("new-name")
    window.project_settings_panel.input_dir_edit.setText("clips")
    window.project_settings_panel.output_dir_edit.setText("renders")

    window._save_project_settings()

    config = window._load_config()
    assert config["project"]["name"] == "new-name"
    assert config["input"]["input_dir"] == "clips"
    assert config["input"]["order_file"] == "clips/order.txt"
    assert config["output"]["output_dir"] == "renders"
    window.close()
    app.processEvents()


def test_main_window_switches_to_selected_project_directory(tmp_path: Path) -> None:
    app = get_app()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (second / "config.yaml").write_text(
        "project:\n  name: second-project\n",
        encoding="utf-8",
    )
    window = MainWindow(first)

    window._switch_project_dir(second)

    assert window.project_dir == second.resolve()
    assert window.project_settings_panel.project_name_edit.text() == "second-project"
    assert window.project_settings_panel.project_dir_label.text() == str(second.resolve())
    window.close()
    app.processEvents()


def test_llm_workflow_tasks_ignore_repeat_click_while_worker_is_active(
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

    window._build_llm_package()
    window._apply_llm_decision()

    assert len(started_workers) == 1
    assert not window.llm_workflow_panel.build_package_button.isEnabled()
    assert not window.llm_workflow_panel.apply_decision_button.isEnabled()
    assert "任务正在运行" in window.log_panel.toPlainText()
    window._finish_worker(started_workers[0], "LLM 视觉证据包完成")
    assert window.llm_workflow_panel.build_package_button.isEnabled()
    assert window.llm_workflow_panel.apply_decision_button.isEnabled()
    window.close()
    app.processEvents()


def test_llm_workflow_panel_saves_manual_blockout_refinement_ratio_before_package_build(
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
    window.llm_workflow_panel.phase_balance_checkbox.setChecked(True)
    window.llm_workflow_panel.blockout_ratio_spin.setValue(1.0)
    window.llm_workflow_panel.refinement_ratio_spin.setValue(2.0)

    window._build_llm_package()

    config = window._load_config()
    assert config["llm_package"]["phase_balance_enabled"] is True
    assert config["llm_package"]["blockout_duration_weight"] == 1.0
    assert config["llm_package"]["refinement_duration_weight"] == 2.0
    assert len(started_workers) == 1
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


def test_node_review_panel_filters_rows_by_label_and_keep_state(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    csv_path = tmp_path / "output" / "cut_decision.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        "node_id,label,keep_in_body_60s,confidence,start_global_time\n"
        "node_0001,hair_detail,true,0.900,1.000\n"
        "node_0002,zoom_pan_view,false,0.300,2.000\n",
        encoding="utf-8",
    )
    window._load_cut_decision()

    window.node_review_panel.filter_edit.setText("hair")
    assert not window.node_review_panel.table.isRowHidden(0)
    assert window.node_review_panel.table.isRowHidden(1)

    window.node_review_panel.filter_edit.clear()
    window.node_review_panel.keep_combo.setCurrentText("删除")
    assert window.node_review_panel.table.isRowHidden(0)
    assert not window.node_review_panel.table.isRowHidden(1)
    window.close()
    app.processEvents()


def test_node_review_panel_sorts_time_numerically(tmp_path: Path) -> None:
    app = get_app()
    window = MainWindow(tmp_path)
    csv_path = tmp_path / "output" / "cut_decision.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        "node_id,label,start_global_time,confidence\n"
        "node_0010,hair_detail,10.000,0.200\n"
        "node_0002,hair_detail,2.000,0.900\n",
        encoding="utf-8",
    )
    window._load_cut_decision()

    window.node_review_panel.sort_combo.setCurrentText("按时间升序")

    assert window.node_review_panel.table.item(0, 0).text() == "node_0002"
    assert window.node_review_panel.table.item(1, 0).text() == "node_0010"
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
