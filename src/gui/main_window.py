from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QMainWindow,
    QProgressBar,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.core.config_manager import ConfigManager
from src.core.file_collector import collect_videos, write_order_file
from src.core.logging_setup import ProjectLogger
from src.core.pipeline import FoundationPipeline
from src.gui.input_panel import InputPanel
from src.gui.log_panel import LogPanel
from src.gui.processing_panel import ProcessingPanel
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

        root = QWidget()
        root_layout = QVBoxLayout(root)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.navigation = QListWidget()
        self.navigation.addItems(["项目设置", "素材管理", "基础处理", "日志"])
        self.pages = QStackedWidget()
        self.pages.addWidget(QLabel("项目设置"))
        self.input_panel = InputPanel()
        self.pages.addWidget(self.input_panel)
        self.processing_panel = ProcessingPanel()
        self.pages.addWidget(self.processing_panel)
        self.pages.addWidget(QLabel("日志"))

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

        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.input_panel.scan_requested.connect(self._scan_inputs)
        self.input_panel.save_order_requested.connect(self._save_input_order)
        self.processing_panel.run_foundation.clicked.connect(self._run_foundation)

    def _load_config(self) -> dict[str, Any]:
        return ConfigManager(self.project_dir).load()

    def _input_paths(self, config: dict[str, Any]) -> tuple[Path, Path]:
        input_config = _section(config, "input")
        input_dir = self.project_dir / str(input_config.get("input_dir", "input"))
        order_file = self.project_dir / str(
            input_config.get("order_file", "input/order.txt")
        )
        return input_dir, order_file

    def _logs_dir(self, config: dict[str, Any]) -> Path:
        output_config = _section(config, "output")
        return self.project_dir / str(output_config.get("logs_dir", "logs"))

    def _scan_inputs(self) -> None:
        try:
            config = self._load_config()
            input_dir, order_file = self._input_paths(config)
            result = collect_videos(input_dir, order_file)
        except Exception as error:
            self.log_panel.append_log(f"扫描失败: {error}")
            return
        self.input_panel.set_files([item.path for item in result.files])
        for warning in result.warnings:
            self.log_panel.append_log("warning: " + warning)

    def _save_input_order(self) -> None:
        if not self.input_panel.ordered_names():
            self.log_panel.append_log("请先扫描素材，再保存 order.txt")
            return
        try:
            config = self._load_config()
            _input_dir, order_file = self._input_paths(config)
            write_order_file(order_file, self.input_panel.ordered_names())
        except Exception as error:
            self.log_panel.append_log(f"保存素材顺序失败: {error}")
            return
        self.log_panel.append_log(f"已保存素材顺序: {order_file}")

    def _run_foundation(self) -> None:
        if self.active_workers:
            self.log_panel.append_log("基础处理正在运行，请等待当前任务完成")
            return

        def task(signals: WorkerSignals) -> None:
            config = self._load_config()
            pipeline = FoundationPipeline(
                self.project_dir,
                config,
                log=ProjectLogger(self._logs_dir(config), sink=signals.log.emit),
                progress=signals.progress.emit,
            )
            pipeline.run_all()

        worker = TaskWorker(task, "基础处理")
        worker.signals.log.connect(self.log_panel.append_log)
        worker.signals.progress.connect(self._set_progress)
        worker.signals.succeeded.connect(lambda message: self._finish_worker(worker, message))
        worker.signals.failed.connect(lambda message: self._finish_worker(worker, message))
        self.active_workers.add(worker)
        self.processing_panel.run_foundation.setEnabled(False)
        self.thread_pool.start(worker)

    def _set_progress(self, value: int, message: str) -> None:
        self.progress_bar.setValue(value)
        self.log_panel.append_log(message)

    def _finish_worker(self, worker: TaskWorker, message: str) -> None:
        self.log_panel.append_log(message)
        self.active_workers.discard(worker)
        if not self.active_workers:
            self.processing_panel.run_foundation.setEnabled(True)
