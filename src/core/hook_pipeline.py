from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.base_processing import OutputVideoSettings, build_output_filter
from src.core.cut_decision_applier import CommandRunner
from src.core.ffmpeg_runner import FFmpegRunner
from src.core.project_manifest import ProjectManifest


@dataclass(frozen=True)
class HookResult:
    normalized_hook: Path
    outputs: list[Path]


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class HookPipeline:
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
        self.runner = runner or FFmpegRunner(self.log)

    @property
    def output_dir(self) -> Path:
        output = _section(self.config, "output")
        return (self.project_dir / str(output.get("output_dir", "output"))).resolve()

    def run_all(self) -> HookResult:
        hook_config = _section(self.config, "external_hook")
        if not hook_config.get("enabled", False):
            raise ValueError("Blender Hook 未启用")
        if not hook_config.get("concat_with_body_cut", True):
            raise ValueError("Blender Hook 自动拼接未启用")
        hook_value = str(hook_config.get("hook_video_path", "")).strip()
        if not hook_value:
            raise ValueError("未设置 Blender Hook 视频路径")
        hook = Path(hook_value)
        if not hook.is_absolute():
            hook = (self.project_dir / hook).resolve()
        if not hook.exists():
            raise FileNotFoundError(f"找不到 Blender Hook 视频: {hook}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        normalized_hook = self.output_dir / "normalized_hook.mp4"
        self._update(15, "规范化 Blender Hook")
        self._normalize_hook(hook, normalized_hook)

        versions = [
            ("body_cut_45s.mp4", "final_with_hook_45s.mp4"),
            ("body_cut_60s.mp4", "final_with_hook_60s.mp4"),
            ("body_cut_120s.mp4", "final_with_hook_120s.mp4"),
        ]
        available = [
            (self.output_dir / body_name, self.output_dir / final_name)
            for body_name, final_name in versions
            if (self.output_dir / body_name).exists()
        ]
        if not available:
            raise FileNotFoundError("没有可拼接的 body_cut_45s/60s/120s.mp4")

        outputs: list[Path] = []
        video = _section(self.config, "output_video")
        fps = int(video.get("fps", 30))
        pixel_format = str(video.get("pixel_format", "yuv420p"))
        for index, (body_cut, final_output) in enumerate(available):
            self._update(35 + int((index / len(available)) * 55), f"拼接 {final_output.name}")
            self.runner.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(normalized_hook),
                    "-i",
                    str(body_cut),
                    "-filter_complex",
                    "[0:v][1:v]concat=n=2:v=1:a=0[outv]",
                    "-map",
                    "[outv]",
                    "-r",
                    str(fps),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    pixel_format,
                    "-an",
                    str(final_output),
                ]
            )
            outputs.append(final_output)
            self.log(f"输出: {final_output}")
        ProjectManifest(self.project_dir, self.config).refresh()
        self._update(100, "Blender Hook 拼接完成")
        return HookResult(normalized_hook=normalized_hook, outputs=outputs)

    def _normalize_hook(self, source: Path, output: Path) -> None:
        video = _section(self.config, "output_video")
        width = int(video.get("width", 1080))
        height = int(video.get("height", 1920))
        fps = int(video.get("fps", 30))
        pixel_format = str(video.get("pixel_format", "yuv420p"))
        expected_duration = float(
            _section(self.config, "external_hook").get(
                "expected_duration_seconds",
                2.0,
            )
        )
        settings = OutputVideoSettings(
            width=width,
            height=height,
            fps=fps,
            pixel_format=pixel_format,
            crop_mode=str(video.get("crop_mode", "center")),
            custom_crop_x=int(video.get("custom_crop_x", 0)),
            custom_crop_y=int(video.get("custom_crop_y", 0)),
            custom_crop_w=int(video.get("custom_crop_w", 0)),
            custom_crop_h=int(video.get("custom_crop_h", 0)),
        )
        self.runner.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-vf",
                build_output_filter(settings),
                "-t",
                str(expected_duration),
                "-r",
                str(fps),
                "-c:v",
                "libx264",
                "-pix_fmt",
                pixel_format,
                "-an",
                str(output),
            ]
        )

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)
