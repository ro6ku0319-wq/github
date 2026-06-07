from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.image_io import read_image, write_image
from src.core.timecode import format_timecode
from src.core.project_manifest import ProjectManifest


@dataclass(frozen=True)
class LlmPackageResult:
    package_dir: Path
    frame_count: int


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class LlmPackageBuilder:
    def __init__(
        self,
        project_dir: Path,
        config: dict[str, Any],
        log: Callable[[str], None] | None = None,
        progress: Callable[[int, str], None] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config = config
        self.log = log or (lambda message: None)
        self.progress = progress or (lambda value, message: None)

    @property
    def output_dir(self) -> Path:
        output = _section(self.config, "output")
        return (self.project_dir / str(output.get("output_dir", "output"))).resolve()

    def build(self) -> LlmPackageResult:
        required = [
            self.output_dir / "frame_manifest.json",
            self.output_dir / "operation_score_table.csv",
            self.output_dir / "cut_decision.csv",
            self.output_dir / "node_contact_sheet.jpg",
        ]
        for path in required:
            if not path.exists():
                raise FileNotFoundError(f"缺少 {path.name}，请先运行节点分析")

        package = self.output_dir / "llm_review_package"
        frames_dir = package / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        for stale_frame in frames_dir.glob("F*.jpg"):
            stale_frame.unlink()
        self._update(10, "读取节点分析结果")
        manifest = json.loads(required[0].read_text(encoding="utf-8"))
        samples = manifest.get("samples", [])
        if not isinstance(samples, list) or not samples:
            raise ValueError("frame_manifest.json 中没有可用抽帧")
        scores = self._read_scores(required[1])
        candidates = self._read_candidates(required[2])

        self._update(35, "整理 LLM 证据帧")
        package_frames = self._copy_frames(samples, frames_dir, candidates)
        (package / "frame_manifest.json").write_text(
            json.dumps({"frames": package_frames}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        shutil.copy2(required[2], package / "operation_candidates.csv")
        shutil.copy2(required[3], package / "node_contact_sheet_01.jpg")

        self._update(65, "生成 LLM 联系图")
        overview_interval = float(
            _section(self.config, "llm_package").get(
                "overview_sample_interval_seconds",
                2,
            )
        )
        overview = self._overview_frames(package_frames, overview_interval)
        high_detail = sorted(
            package_frames,
            key=lambda item: scores.get(str(item["source_sample_id"]), 0.0),
            reverse=True,
        )[: min(24, len(package_frames))]
        _write_frame_sheet(package / "overview_contact_sheet.jpg", overview)
        _write_frame_sheet(package / "high_detail_contact_sheet.jpg", high_detail)

        self._update(90, "生成 llm_prompt.md")
        (package / "llm_prompt.md").write_text(_prompt_text(), encoding="utf-8")
        ProjectManifest(self.project_dir, self.config).refresh()
        self._update(100, "LLM 视觉证据包完成")
        return LlmPackageResult(package_dir=package, frame_count=len(package_frames))

    def _copy_frames(
        self,
        samples: list[dict[str, Any]],
        frames_dir: Path,
        candidates: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        copied: list[dict[str, Any]] = []
        for index, sample in enumerate(samples, start=1):
            source = Path(str(sample.get("image_path", "")))
            if not source.is_absolute():
                source = (self.project_dir / source).resolve()
            if not source.exists():
                self.log(f"跳过缺失证据帧: {source}")
                continue
            frame_id = f"F{index:03d}"
            destination = frames_dir / f"{frame_id}.jpg"
            shutil.copy2(source, destination)
            seconds = float(sample.get("time_seconds", 0.0))
            copied.append(
                {
                    "frame_id": frame_id,
                    "global_timecode": format_timecode(seconds),
                    "source_file": "accelerated_base.mp4",
                    "source_timecode": format_timecode(seconds),
                    "image_file": f"frames/{destination.name}",
                    "candidate_node_id": _candidate_at(seconds, candidates),
                    "source_sample_id": sample.get("sample_id", ""),
                }
            )
        if not copied:
            raise ValueError("没有可复制到 LLM 证据包的帧")
        return copied

    @staticmethod
    def _read_scores(path: Path) -> dict[str, float]:
        with path.open(encoding="utf-8", newline="") as handle:
            return {
                row.get("sample_id", ""): float(row.get("activity_score", 0.0))
                for row in csv.DictReader(handle)
            }

    @staticmethod
    def _read_candidates(path: Path) -> list[dict[str, str]]:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _overview_frames(
        frames: list[dict[str, Any]],
        interval_seconds: float,
    ) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        next_time = 0.0
        for frame in frames:
            current = _timecode_seconds(str(frame["global_timecode"]))
            if current + 1e-6 >= next_time:
                selected.append(frame)
                next_time = current + max(0.1, interval_seconds)
        return selected or frames[:1]

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)


def _candidate_at(seconds: float, candidates: list[dict[str, str]]) -> str | None:
    for candidate in candidates:
        try:
            start = float(candidate.get("start_global_time", ""))
            end = float(candidate.get("end_global_time", ""))
        except ValueError:
            continue
        if start <= seconds <= end:
            return candidate.get("node_id") or None
    return None


def _timecode_seconds(value: str) -> float:
    hours, minutes, seconds = value.split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _write_frame_sheet(path: Path, frames: list[dict[str, Any]]) -> None:
    visible = frames[:60]
    columns = min(5, max(1, len(visible)))
    cell_width = 220
    cell_height = 360
    rows = max(1, int(np.ceil(len(visible) / columns)))
    canvas = np.full((rows * cell_height, columns * cell_width, 3), 250, dtype=np.uint8)
    for index, frame in enumerate(visible):
        image_path = path.parent / str(frame["image_file"])
        image = read_image(image_path)
        thumbnail = _fit(image, cell_width - 20, cell_height - 76)
        x = (index % columns) * cell_width
        y = (index // columns) * cell_height
        left = x + (cell_width - thumbnail.shape[1]) // 2
        canvas[y + 8 : y + 8 + thumbnail.shape[0], left : left + thumbnail.shape[1]] = thumbnail
        cv2.putText(
            canvas,
            f"{frame['frame_id']} {frame['global_timecode']}",
            (x + 8, y + cell_height - 42),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            str(frame.get("candidate_node_id") or "no-node"),
            (x + 8, y + cell_height - 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )
    write_image(path, canvas, ".jpg")


def _fit(image: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height)
    return cv2.resize(
        image,
        (max(1, int(width * scale)), max(1, int(height * scale))),
        interpolation=cv2.INTER_AREA,
    )


def _prompt_text() -> str:
    return """# OB11 ZBrush Body Cut LLM 剪辑任务

你是一个熟悉 ZBrush、OB11 头壳、小红书缩时视频节奏的剪辑顾问。

请根据 overview_contact_sheet.jpg、node_contact_sheet_01.jpg、
high_detail_contact_sheet.jpg、frame_manifest.json 和 operation_candidates.csv，
输出严格 JSON 格式的 edit_decision.json。

注意：
- 你不能知道真实 ZBrush 命令，不要编造真实笔刷名称。
- 只根据画面判断视觉阶段和剪辑价值。
- 只负责雕刻过程 body cut，不选择或生成 Blender hook。
- body cut 第 0 秒直接进入雕刻过程，主发布版目标约 60 秒。
- 前 20 秒应有 2–3 个明显变化节点。
- 发型、五官、配件、完成展示优先；后发、发尾、UI、重复调整低优先。

必须使用以下顶层结构：

```json
{
  "video_type": "body_cut_only",
  "external_hook": {
    "provided_by_user": true,
    "generated_by": "Blender",
    "not_included_in_this_decision": true,
    "expected_duration_seconds": 2
  },
  "recommended_body_duration_seconds": 60,
  "first_20_seconds_body_plan": [],
  "segments": [],
  "cover_candidates": [],
  "davinci_markers": [],
  "notes_for_human_editor": []
}
```

每个 segments 项必须包含 node_id、label、label_cn、start_global_time、
end_global_time、edit_action、include_in_body_45s、include_in_body_60s、
include_in_body_120s、output_duration_seconds、speed_multiplier、rhythm_role、
requires_final_position、result_visible_at_next_node 和 reason。
"""
