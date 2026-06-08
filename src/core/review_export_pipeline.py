from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.cut_decision_applier import (
    CommandRunner,
    CutDecisionApplier,
    read_cut_decisions,
    select_segments,
)
from src.core.davinci_marker_exporter import write_davinci_markers_csv
from src.core.ffmpeg_runner import FFmpegRunner
from src.core.project_manifest import ProjectManifest


@dataclass(frozen=True)
class ReviewExportResult:
    body_cut_outputs: list[Path]
    preview_output: Path
    marker_output: Path


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class ReviewExportPipeline:
    def __init__(
        self,
        project_dir: Path,
        config: dict[str, Any],
        log: Callable[[str], None] | None = None,
        progress: Callable[[int, str], None] | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config = config
        self.log = log or (lambda message: None)
        self.progress = progress or (lambda value, message: None)
        output_video = _section(config, "output_video")
        self.applier = CutDecisionApplier(
            runner or FFmpegRunner(self.log),
            pixel_format=str(output_video.get("pixel_format", "yuv420p")),
        )

    @property
    def output_dir(self) -> Path:
        output = _section(self.config, "output")
        return (self.project_dir / str(output.get("output_dir", "output"))).resolve()

    def run_all(self) -> ReviewExportResult:
        source = self.output_dir / "accelerated_base.mp4"
        decision_path = self.output_dir / "cut_decision.csv"
        if not source.exists():
            raise FileNotFoundError(
                f"缺少 {source.name}，请先运行基础处理生成 output/accelerated_base.mp4"
            )
        if not decision_path.exists():
            raise FileNotFoundError(
                f"缺少 {decision_path.name}，请先运行节点分析生成 output/cut_decision.csv"
            )

        self._update(10, "读取 cut_decision.csv")
        decisions = read_cut_decisions(decision_path)
        outputs: list[Path] = []
        versions = _section(self.config, "cut_versions")
        enabled_versions = [
            ("body_45s", "body_cut_45s.mp4", 45.0),
            ("body_60s", "body_cut_60s.mp4", 60.0),
            ("body_120s", "body_cut_120s.mp4", 120.0),
        ]
        for index, (version, filename, default_target) in enumerate(enabled_versions):
            settings = versions.get(version, {})
            if isinstance(settings, dict) and not settings.get("enabled", True):
                continue
            target = default_target
            if isinstance(settings, dict):
                target = float(settings.get("target_duration_seconds", default_target))
            segments = select_segments(decisions, version, target)
            if not segments:
                self.log(f"跳过 {filename}: 没有勾选片段")
                continue
            output = self.output_dir / filename
            self._update(20 + (index * 20), f"导出 {filename}")
            self.applier.create_cut(source, output, segments)
            outputs.append(output)
            self.log(f"输出: {output}")

        self._update(80, "导出 auto_node_preview.mp4")
        preview_segments = select_segments(decisions, "body_120s", None)
        if not preview_segments:
            preview_segments = [item for item in decisions if item.end_global_time > item.start_global_time]
        preview_output = self.output_dir / "auto_node_preview.mp4"
        if preview_segments:
            self.applier.create_cut(source, preview_output, preview_segments)
            self.log(f"输出: {preview_output}")

        self._update(92, "导出 DaVinci markers")
        marker_output = self.output_dir / "davinci_markers.csv"
        write_davinci_markers_csv(marker_output, decisions)
        self.log(f"输出: {marker_output}")

        ProjectManifest(self.project_dir, self.config).refresh()
        self._update(100, "导出完成")
        return ReviewExportResult(
            body_cut_outputs=outputs,
            preview_output=preview_output,
            marker_output=marker_output,
        )

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)
