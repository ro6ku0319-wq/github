from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from src.core.base_processing import BaseProcessor, OutputVideoSettings
from src.core.ffmpeg_runner import FFmpegRunner
from src.core.file_collector import CollectionResult, InputVideo, collect_videos
from src.core.report_writer import (
    dataclass_list,
    write_edit_report_text,
    write_input_order,
    write_json,
)
from src.core.timeline_mapper import TimelineRange, build_timeline
from src.core.video_probe import VideoMetadata, probe_video


def _config_section(config: dict[str, Any], name: str) -> dict[str, Any]:
    section = config.get(name, {})
    return section if isinstance(section, dict) else {}


class FoundationPipeline:
    def __init__(
        self,
        project_dir: Path,
        config: dict[str, Any],
        log: Callable[[str], None] | None = None,
        progress: Callable[[int, str], None] | None = None,
        processor: BaseProcessor | None = None,
        tool_validator: Callable[[], None] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config = config
        self.log = log or (lambda message: None)
        self.progress = progress or (lambda value, message: None)

        output_video = _config_section(config, "output_video")
        settings = OutputVideoSettings(
            width=int(output_video.get("width", 1080)),
            height=int(output_video.get("height", 1920)),
            fps=int(output_video.get("fps", 30)),
            pixel_format=str(output_video.get("pixel_format", "yuv420p")),
        )
        self.processor = processor or BaseProcessor(FFmpegRunner(self.log), settings)
        self.tool_validator = tool_validator or FFmpegRunner.validate_tools

    @property
    def output_dir(self) -> Path:
        output = _config_section(self.config, "output")
        return (self.project_dir / str(output.get("output_dir", "output"))).resolve()

    def collect(self) -> CollectionResult:
        input_config = _config_section(self.config, "input")
        input_dir = (
            self.project_dir / str(input_config.get("input_dir", "input"))
        ).resolve()
        order_file = (
            self.project_dir / str(input_config.get("order_file", "input/order.txt"))
        ).resolve()
        return collect_videos(input_dir, order_file)

    def probe(self, files: Iterable[InputVideo]) -> list[VideoMetadata]:
        readable: list[VideoMetadata] = []
        for item in files:
            try:
                readable.append(probe_video(item.path))
            except Exception as error:
                self.log(f"跳过无法读取的视频: {item.path} ({error})")
        if not readable:
            raise RuntimeError("所有输入视频都无法读取，基础处理终止。")
        return readable

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)

    def _acceleration_factor(self) -> float:
        processing = _config_section(self.config, "base_processing")
        return float(processing.get("acceleration_factor", 8.0))

    def _write_reports(
        self,
        collection: CollectionResult,
        metadata: list[VideoMetadata],
        timeline: list[TimelineRange],
    ) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        write_input_order(self.output_dir / "input_order.txt", collection, timeline)
        write_json(
            self.output_dir / "edit_report.json",
            {
                "videos": dataclass_list(metadata),
                "timeline": dataclass_list(timeline),
                "warnings": collection.warnings,
            },
        )
        write_edit_report_text(
            self.output_dir / "edit_report.txt",
            metadata,
            timeline,
            collection.warnings,
        )

    def create_full_concat(self, metadata: list[VideoMetadata]) -> None:
        self.processor.create_full_concat(
            [item.path for item in metadata],
            self.output_dir / "full_concat.mp4",
            self.output_dir / "concat_list.txt",
        )

    def create_accelerated_base(self) -> None:
        self.processor.create_accelerated_base(
            self.output_dir / "full_concat.mp4",
            self.output_dir / "accelerated_base.mp4",
            self._acceleration_factor(),
        )

    def run_all(self) -> None:
        self.tool_validator()
        self._update(5, "扫描输入素材")
        collection = self.collect()
        self._update(15, "读取视频元数据")
        metadata = self.probe(collection.files)
        timeline = build_timeline(metadata)
        self._write_reports(collection, metadata, timeline)

        self._update(30, "生成 full_concat.mp4")
        full_concat = self.output_dir / "full_concat.mp4"
        accelerated_base = self.output_dir / "accelerated_base.mp4"
        self.create_full_concat(metadata)
        self.log(f"输出: {full_concat}")

        self._update(70, "生成 accelerated_base.mp4")
        self.create_accelerated_base()
        self.log(f"输出: {accelerated_base}")
        self._update(100, "基础处理完成")
