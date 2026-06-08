from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class CommandRunner(Protocol):
    def run(self, command: list[str]) -> None:
        pass


@dataclass(frozen=True)
class OutputVideoSettings:
    width: int
    height: int
    fps: int
    pixel_format: str
    crop_mode: str = "center"
    custom_crop_x: int = 0
    custom_crop_y: int = 0
    custom_crop_w: int = 0
    custom_crop_h: int = 0


def build_output_filter(settings: OutputVideoSettings) -> str:
    width = settings.width
    height = settings.height
    if settings.crop_mode == "fit":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
        )
    if settings.crop_mode == "custom":
        crop_w = settings.custom_crop_w or width
        crop_h = settings.custom_crop_h or height
        if min(crop_w, crop_h) <= 0:
            raise ValueError("自定义裁剪宽高必须大于 0")
        return (
            f"crop={crop_w}:{crop_h}:{settings.custom_crop_x}:{settings.custom_crop_y},"
            f"scale={width}:{height}"
        )
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )


class BaseProcessor:
    def __init__(self, runner: CommandRunner, settings: OutputVideoSettings) -> None:
        self.runner = runner
        self.settings = settings

    def _output_filter(self) -> str:
        return build_output_filter(self.settings)

    def create_full_concat(
        self,
        videos: list[Path],
        output: Path,
        concat_list: Path,
    ) -> None:
        if not videos:
            raise ValueError("至少需要一个输入视频")

        output.parent.mkdir(parents=True, exist_ok=True)
        concat_list.parent.mkdir(parents=True, exist_ok=True)
        concat_list.write_text(
            "".join(
                f"file '{self._escape_concat_path(video)}'\n" for video in videos
            ),
            encoding="utf-8",
        )
        self.runner.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-vf",
                self._output_filter(),
                "-r",
                str(self.settings.fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                self.settings.pixel_format,
                "-an",
                str(output),
            ]
        )

    def create_accelerated_base(
        self,
        source: Path,
        output: Path,
        factor: float,
    ) -> None:
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("加速倍数必须大于 0")

        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vf",
                f"setpts=PTS/{factor}",
                "-r",
                str(self.settings.fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                self.settings.pixel_format,
                "-an",
                str(output),
            ]
        )

    @staticmethod
    def _escape_concat_path(path: Path) -> str:
        return path.resolve().as_posix().replace("'", "'\\''")
