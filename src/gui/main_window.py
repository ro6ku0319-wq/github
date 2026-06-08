from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThreadPool, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QListWidget,
    QMainWindow,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config_manager import ConfigManager
from src.core.codex_decision_pipeline import CodexDecisionPipeline
from src.core.editing_profile import EditingProfileManager
from src.core.file_collector import collect_videos, write_order_file
from src.core.hook_pipeline import HookPipeline
from src.core.llm_decision_pipeline import LlmDecisionPipeline
from src.core.llm_package_builder import LlmPackageBuilder
from src.core.logging_setup import ProjectLogger
from src.core.node_analysis_pipeline import NodeAnalysisPipeline
from src.core.output_resolution import (
    DEFAULT_RESOLUTION_PRESET,
    get_resolution_preset,
    preset_key_for_size,
)
from src.core.pipeline import FoundationPipeline
from src.core.project_manifest import ProjectManifest
from src.core.review_export_pipeline import ReviewExportPipeline
from src.gui.hook_panel import HookPanel
from src.gui.input_panel import InputPanel
from src.gui.llm_apply_panel import LlmApplyPanel
from src.gui.llm_workflow_panel import LlmWorkflowPanel
from src.gui.log_panel import LogPanel
from src.gui.log_viewer_panel import LogViewerPanel
from src.gui.node_review_panel import NodeReviewPanel
from src.gui.preview_panel import PreviewPanel
from src.gui.processing_panel import ProcessingPanel
from src.gui.project_settings_panel import ProjectSettingsPanel
from src.gui.settings_panel import SettingsPanel
from src.gui.workers import TaskWorker, WorkerSignals


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class MainWindow(QMainWindow):
    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = Path(project_dir).resolve()
        self.thread_pool = QThreadPool.globalInstance()
        self.active_workers: set[TaskWorker] = set()
        self.setWindowTitle("OB11 ZBrush Body Cut")

        config = self._load_config()
        root = QWidget()
        root_layout = QVBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.navigation = QListWidget()
        self.navigation.addItems(
            [
                "项目设置",
                "素材管理",
                "基础处理",
                "节点审查",
                "预览",
                "LLM 证据包",
                "应用 LLM 决策",
                "Blender Hook",
                "通用设置",
                "日志",
            ]
        )
        self.pages = QStackedWidget()

        self.project_settings_panel = ProjectSettingsPanel()
        self.project_settings_panel.load_config(self.project_dir, config)
        self.pages.addWidget(self.project_settings_panel)
        self.input_panel = InputPanel()
        self.pages.addWidget(self.input_panel)
        self.processing_panel = ProcessingPanel()
        self._load_resolution(config)
        self.pages.addWidget(self.processing_panel)
        self.node_review_panel = NodeReviewPanel()
        self.pages.addWidget(self.node_review_panel)
        self.preview_panel = PreviewPanel()
        self.pages.addWidget(self.preview_panel)
        self.llm_workflow_panel = LlmWorkflowPanel()
        self.llm_workflow_panel.load_config(config)
        self.pages.addWidget(self.llm_workflow_panel)
        self.llm_apply_panel = LlmApplyPanel()
        self.pages.addWidget(self.llm_apply_panel)
        self.hook_panel = HookPanel()
        self.hook_panel.load_config(_section(config, "external_hook"))
        self.pages.addWidget(self.hook_panel)
        self.settings_panel = SettingsPanel()
        self.settings_panel.load_config(config)
        self.pages.addWidget(self.settings_panel)
        self.log_viewer_panel = LogViewerPanel()
        self.pages.addWidget(self.log_viewer_panel)

        splitter.addWidget(self.navigation)
        splitter.addWidget(self.pages)
        splitter.setStretchFactor(1, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.log_panel = LogPanel()
        root_layout.addWidget(splitter)
        root_layout.addWidget(self.progress_bar)
        root_layout.addWidget(self.log_panel)
        self.setCentralWidget(root)
        self._connect_signals()
        self.navigation.setCurrentRow(0)
        self._refresh_preview()
        self._refresh_logs()

    def _connect_signals(self) -> None:
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.input_panel.scan_requested.connect(self._scan_inputs)
        self.input_panel.save_order_requested.connect(self._save_input_order)
        self.processing_panel.run_foundation.clicked.connect(self._run_foundation)
        self.processing_panel.run_node_analysis.clicked.connect(self._run_node_analysis)
        self.processing_panel.run_exports.clicked.connect(self._run_exports)
        self.processing_panel.resolution_combo.currentIndexChanged.connect(
            self._save_output_resolution_preset
        )
        self.node_review_panel.refresh_requested.connect(self._load_cut_decision)
        self.node_review_panel.save_requested.connect(self._save_cut_decision)
        self.node_review_panel.open_folder_requested.connect(self._open_output_dir)
        self.llm_workflow_panel.build_package_button.clicked.connect(
            self._build_llm_package
        )
        self.llm_workflow_panel.codex_generate_button.clicked.connect(
            self._codex_generate_decision
        )
        self.llm_workflow_panel.apply_decision_button.clicked.connect(
            lambda: self._apply_llm_decision(
                self.llm_workflow_panel.selected_decision_path()
            )
        )
        self.llm_apply_panel.apply_requested.connect(self._apply_llm_decision)
        self.llm_apply_panel.confirm_requested.connect(self._confirm_llm_decision)
        self.hook_panel.save_button.clicked.connect(self._save_hook_settings)
        self.hook_panel.export_button.clicked.connect(self._export_with_hook)
        self.preview_panel.refresh_requested.connect(self._refresh_preview)
        self.preview_panel.open_output_requested.connect(self._open_output_dir)
        self.preview_panel.open_path_requested.connect(self._open_output_path)
        self.project_settings_panel.save_requested.connect(self._save_project_settings)
        self.project_settings_panel.reload_requested.connect(self._reload_settings)
        self.project_settings_panel.open_project_requested.connect(
            lambda: self._open_path(self.project_dir)
        )
        self.project_settings_panel.open_output_requested.connect(self._open_output_dir)
        self.project_settings_panel.project_directory_selected.connect(
            self._switch_project_dir
        )
        self.settings_panel.save_requested.connect(self._save_general_settings)
        self.log_viewer_panel.refresh_requested.connect(self._refresh_logs)
        self.log_viewer_panel.open_logs_requested.connect(self._open_logs_dir)

    def _load_config(self) -> dict[str, Any]:
        return ConfigManager(self.project_dir).load()

    def _load_resolution(self, config: dict[str, Any]) -> None:
        output_video = _section(config, "output_video")
        width = int(output_video.get("width", 1080))
        height = int(output_video.get("height", 1920))
        current = str(output_video.get("resolution_preset", DEFAULT_RESOLUTION_PRESET))
        try:
            preset = get_resolution_preset(current)
        except ValueError:
            current = preset_key_for_size(width, height)
        else:
            if (preset.width, preset.height) != (width, height):
                current = preset_key_for_size(width, height)
        self.processing_panel.select_resolution(current)

    def _input_paths(self, config: dict[str, Any]) -> tuple[Path, Path]:
        section = _section(config, "input")
        return (
            self.project_dir / str(section.get("input_dir", "input")),
            self.project_dir / str(section.get("order_file", "input/order.txt")),
        )

    def _logs_dir(self, config: dict[str, Any]) -> Path:
        return self.project_dir / str(_section(config, "output").get("logs_dir", "logs"))

    def _output_dir(self, config: dict[str, Any]) -> Path:
        return self.project_dir / str(
            _section(config, "output").get("output_dir", "output")
        )

    def _save_output_resolution_preset(self, _index: int) -> None:
        key = self.processing_panel.resolution_combo.currentData()
        try:
            preset = get_resolution_preset(
                key if isinstance(key, str) else DEFAULT_RESOLUTION_PRESET
            )
            manager = ConfigManager(self.project_dir)
            config = manager.load()
            section = _section(config, "output_video")
            section.update(
                {
                    "resolution_preset": preset.key,
                    "width": preset.width,
                    "height": preset.height,
                }
            )
            config["output_video"] = section
            manager.save(config)
        except Exception as error:
            self.log_panel.append_log(f"保存输出分辨率失败: {error}")
            return
        self.log_panel.append_log(f"已设置输出分辨率: {preset.label}")

    def _scan_inputs(self) -> None:
        try:
            input_dir, order_file = self._input_paths(self._load_config())
            result = collect_videos(input_dir, order_file)
        except Exception as error:
            self.log_panel.append_log(f"扫描失败: {error}")
            return
        self.input_panel.set_files([item.path for item in result.files])
        for warning in result.warnings:
            self.log_panel.append_log("warning: " + warning)

    def _save_input_order(self) -> None:
        names = self.input_panel.ordered_names()
        if not names:
            self.log_panel.append_log("请先扫描素材，再保存 order.txt")
            return
        try:
            _input_dir, order_file = self._input_paths(self._load_config())
            write_order_file(order_file, names)
        except Exception as error:
            self.log_panel.append_log(f"保存素材顺序失败: {error}")
            return
        self.log_panel.append_log(f"已保存素材顺序: {order_file}")
        self._refresh_manifest(source_files=names, input_order=names)

    def _run_foundation(self) -> None:
        if self.active_workers:
            self.log_panel.append_log("基础处理正在运行，请等待当前任务完成")
            return
        self._start_pipeline(
            "基础处理",
            lambda config, signals: FoundationPipeline(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            ).run_all(),
        )

    def _run_node_analysis(self) -> None:
        self._start_pipeline(
            "节点分析",
            lambda config, signals: NodeAnalysisPipeline(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            ).run_all(),
            load_decisions=True,
        )

    def _run_exports(self) -> None:
        self._start_pipeline(
            "导出 body cut",
            lambda config, signals: ReviewExportPipeline(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            ).run_all(),
        )

    def _build_llm_package(self) -> None:
        if not self._save_llm_package_settings():
            return
        self._start_pipeline(
            "LLM 视觉证据包",
            lambda config, signals: LlmPackageBuilder(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            ).build(),
        )

    def _codex_generate_decision(self) -> None:
        if not self._save_llm_package_settings():
            return
        self._start_pipeline(
            "Codex 生成剪辑说明书",
            lambda config, signals: CodexDecisionPipeline(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            ).generate(),
            load_llm_decision=True,
        )

    def _apply_llm_decision(self, decision_path: Path | None = None) -> None:
        path = (
            decision_path
            or self.llm_apply_panel.selected_decision_path()
            or self.llm_workflow_panel.selected_decision_path()
        )
        self._start_pipeline(
            "应用 LLM 剪辑说明书",
            lambda config, signals: LlmDecisionPipeline(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            ).apply(path),
        )

    def _confirm_llm_decision(self) -> None:
        try:
            output = self._output_dir(self._load_config()) / "llm_result"
            result = EditingProfileManager().confirm_decision(
                output / "codex_generated_edit_decision.json",
                output / "edit_decision.json",
                project_name=str(_section(self._load_config(), "project").get("name", self.project_dir.name)),
            )
        except Exception as error:
            self.log_panel.append_log(f"确认最终方案并学习失败: {error}")
            return
        self.log_panel.append_log(
            f"确认最终方案并学习完成，样本数: {result.sample_count}"
        )

    def _export_with_hook(self) -> None:
        if self.active_workers:
            self.log_panel.append_log("任务正在运行，请等待当前任务完成")
            return
        if not self._save_hook_settings():
            return
        self._start_pipeline(
            "Blender Hook 拼接",
            lambda config, signals: HookPipeline(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            ).run_all(),
        )

    def _start_pipeline(
        self,
        name: str,
        operation: Any,
        load_decisions: bool = False,
        load_llm_decision: bool = False,
    ) -> None:
        if self.active_workers:
            self.log_panel.append_log("任务正在运行，请等待当前任务完成")
            return

        def task(signals: WorkerSignals) -> None:
            operation(self._load_config(), signals)

        worker = TaskWorker(task, name)
        worker.signals.log.connect(self.log_panel.append_log)
        worker.signals.progress.connect(self._set_progress)
        if load_decisions:
            worker.signals.succeeded.connect(
                lambda message: self._finish_node_analysis_worker(worker, message)
            )
        elif load_llm_decision:
            worker.signals.succeeded.connect(
                lambda message: self._finish_llm_decision_worker(worker, message)
            )
        else:
            worker.signals.succeeded.connect(
                lambda message: self._finish_worker(worker, message)
            )
        worker.signals.failed.connect(lambda message: self._finish_worker(worker, message))
        self.active_workers.add(worker)
        self._set_processing_enabled(False)
        self.thread_pool.start(worker)

    def _set_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.log_panel.append_log(message)

    def _finish_worker(self, worker: TaskWorker, message: str) -> None:
        self.log_panel.append_log(message)
        self.active_workers.discard(worker)
        if not self.active_workers:
            self._set_processing_enabled(True)
        self._refresh_preview()
        self._refresh_logs()
        self._refresh_manifest()

    def _finish_node_analysis_worker(self, worker: TaskWorker, message: str) -> None:
        self._finish_worker(worker, message)
        self._load_cut_decision()

    def _finish_llm_decision_worker(self, worker: TaskWorker, message: str) -> None:
        self._finish_worker(worker, message)
        try:
            path = self._output_dir(self._load_config()) / "llm_result" / "edit_decision.json"
            self.llm_apply_panel.load_json(path)
            self.pages.setCurrentWidget(self.llm_apply_panel)
            self.navigation.setCurrentRow(6)
        except Exception as error:
            self.log_panel.append_log(f"加载 Codex 生成 JSON 失败: {error}")

    def _set_processing_enabled(self, enabled: bool) -> None:
        self.processing_panel.run_foundation.setEnabled(enabled)
        self.processing_panel.run_node_analysis.setEnabled(enabled)
        self.processing_panel.run_exports.setEnabled(enabled)
        self.llm_workflow_panel.set_actions_enabled(enabled)
        self.llm_apply_panel.set_actions_enabled(enabled)
        self.hook_panel.set_actions_enabled(enabled)
        self.project_settings_panel.set_actions_enabled(enabled)
        self.settings_panel.set_actions_enabled(enabled)

    def _load_cut_decision(self) -> None:
        try:
            self.node_review_panel.load_csv(
                self._output_dir(self._load_config()) / "cut_decision.csv"
            )
        except Exception as error:
            self.log_panel.append_log(f"加载 cut_decision.csv 失败: {error}")
            return
        self.log_panel.append_log("已加载 cut_decision.csv")

    def _save_cut_decision(self) -> None:
        try:
            self.node_review_panel.save_csv(
                self._output_dir(self._load_config()) / "cut_decision.csv"
            )
        except Exception as error:
            self.log_panel.append_log(f"保存 cut_decision.csv 失败: {error}")
            return
        self.log_panel.append_log("已保存 cut_decision.csv")
        self._refresh_manifest()

    def _save_hook_settings(self) -> bool:
        try:
            manager = ConfigManager(self.project_dir)
            config = manager.load()
            section = _section(config, "external_hook")
            section.update(self.hook_panel.config_values())
            config["external_hook"] = section
            manager.save(config)
        except Exception as error:
            self.log_panel.append_log(f"保存 Blender Hook 设置失败: {error}")
            return False
        self.log_panel.append_log("已保存 Blender Hook 设置")
        return True

    def _save_llm_package_settings(self) -> bool:
        try:
            manager = ConfigManager(self.project_dir)
            config = manager.load()
            section = _section(config, "llm_package")
            section.update(self.llm_workflow_panel.config_values())
            config["llm_package"] = section
            manager.save(config)
        except Exception as error:
            self.log_panel.append_log(f"保存 LLM 证据包设置失败: {error}")
            return False
        self.log_panel.append_log("已保存 LLM 证据包设置")
        return True

    def _save_project_settings(self) -> None:
        try:
            values = self.project_settings_panel.config_values()
            manager = ConfigManager(self.project_dir)
            config = manager.load()
            project = _section(config, "project")
            project["name"] = values["project_name"]
            config["project"] = project
            input_config = _section(config, "input")
            input_config["input_dir"] = values["input_dir"]
            input_config["order_file"] = (
                Path(values["input_dir"]) / "order.txt"
            ).as_posix()
            config["input"] = input_config
            output_config = _section(config, "output")
            output_config["output_dir"] = values["output_dir"]
            config["output"] = output_config
            manager.save(config)
        except Exception as error:
            self.log_panel.append_log(f"保存项目设置失败: {error}")
            return
        self.log_panel.append_log("已保存项目设置")
        self._reload_settings()

    def _save_general_settings(self) -> None:
        try:
            values = self.settings_panel.config_values()
            manager = ConfigManager(self.project_dir)
            config = manager.load()
            base = _section(config, "base_processing")
            base["acceleration_factor"] = values["acceleration_factor"]
            config["base_processing"] = base
            video = _section(config, "output_video")
            video.update(
                {
                    "width": values["width"],
                    "height": values["height"],
                    "fps": values["fps"],
                    "crop_mode": values["crop_mode"],
                    "custom_crop_x": values["custom_crop_x"],
                    "custom_crop_y": values["custom_crop_y"],
                    "custom_crop_w": values["custom_crop_w"],
                    "custom_crop_h": values["custom_crop_h"],
                }
            )
            config["output_video"] = video
            fine = _section(config, "fine_cut")
            for key in (
                "coarse_sample_interval_seconds",
                "fine_sample_every_n_frames",
                "boundary_search_window_seconds",
                "completion_hold_frames",
                "min_node_duration_seconds",
            ):
                fine[key] = values[key]
            config["fine_cut"] = fine
            versions = _section(config, "cut_versions")
            for name in ("body_45s", "body_60s", "body_120s"):
                section = versions.get(name, {})
                if not isinstance(section, dict):
                    section = {}
                section["target_duration_seconds"] = values[name]
                versions[name] = section
            config["cut_versions"] = versions
            config["operation_priority"] = values["operation_priority"]
            manager.save(config)
        except Exception as error:
            self.log_panel.append_log(f"保存通用设置失败: {error}")
            return
        self.log_panel.append_log("已保存通用设置")

    def _reload_settings(self) -> None:
        try:
            config = self._load_config()
            self.project_settings_panel.load_config(self.project_dir, config)
            self.settings_panel.load_config(config)
            self.llm_workflow_panel.load_config(config)
            self.hook_panel.load_config(_section(config, "external_hook"))
        except Exception as error:
            self.log_panel.append_log(f"重新加载配置失败: {error}")
            return
        self.log_panel.append_log("已重新加载配置")
        self._refresh_preview()
        self._refresh_logs()

    def _switch_project_dir(self, project_dir: object) -> None:
        if self.active_workers:
            self.log_panel.append_log("任务正在运行，不能切换项目目录")
            return
        path = Path(str(project_dir)).resolve()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self.log_panel.append_log(f"切换项目目录失败: {error}")
            return
        self.project_dir = path
        self.input_panel.set_files([])
        self.node_review_panel.table.setRowCount(0)
        self.log_panel.clear()
        self._reload_settings()
        self.log_panel.append_log(f"已切换项目目录: {path}")

    def _refresh_preview(self) -> None:
        try:
            self.preview_panel.refresh(self._output_dir(self._load_config()))
        except Exception as error:
            self.log_panel.append_log(f"刷新预览失败: {error}")

    def _refresh_logs(self) -> None:
        try:
            self.log_viewer_panel.refresh(self._logs_dir(self._load_config()))
        except Exception as error:
            self.log_panel.append_log(f"刷新日志失败: {error}")

    def _refresh_manifest(
        self,
        source_files: list[str] | None = None,
        input_order: list[str] | None = None,
    ) -> None:
        try:
            ProjectManifest(self.project_dir, self._load_config()).refresh(
                source_files=source_files,
                input_order=input_order,
            )
        except Exception as error:
            self.log_panel.append_log(f"更新 project_manifest.json 失败: {error}")

    def _open_output_dir(self) -> None:
        self._open_path(self._output_dir(self._load_config()))

    def _open_logs_dir(self) -> None:
        self._open_path(self._logs_dir(self._load_config()))

    def _open_output_path(self, value: object) -> None:
        self._open_path(self._output_dir(self._load_config()) / str(value))

    def _open_path(self, path: Path) -> None:
        path = Path(path).resolve()
        if not path.exists():
            self.log_panel.append_log(f"路径不存在: {path}")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.log_panel.append_log(f"无法打开路径: {path}")
