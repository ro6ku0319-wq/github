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


class BaseProcessor:
    def __init__(self, runner: CommandRunner, settings: OutputVideoSettings) -> None:
        self.runner = runner
        self.settings = settings

    def _vertical_filter(self) -> str:
        width = self.settings.width
        height = self.settings.height
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )

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
                self._vertical_filter(),
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
