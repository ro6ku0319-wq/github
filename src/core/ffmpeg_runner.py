from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable


class ToolMissingError(RuntimeError):
    pass


class FFmpegRunner:
    def __init__(self, log: Callable[[str], None] | None = None) -> None:
        self.log = log or logging.getLogger(__name__).info

    @staticmethod
    def validate_tools() -> None:
        for name in ("ffmpeg", "ffprobe"):
            if shutil.which(name) is None:
                raise ToolMissingError(
                    f"未找到 {name}。请安装 FFmpeg 并加入 PATH。"
                )

    def run(self, command: list[str]) -> None:
        self.log("FFmpeg: " + subprocess.list2cmdline(command))
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            self.log(line.strip())
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"FFmpeg 执行失败，退出码: {return_code}")
