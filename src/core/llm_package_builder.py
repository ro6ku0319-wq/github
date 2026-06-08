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
from src.core.editing_profile import EditingProfileManager
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
        EditingProfileManager().snapshot_to(package / "style_profile.yaml")
        (package / "llm_prompt.md").write_text(
            _prompt_text(self.config),
            encoding="utf-8",
        )
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


def _prompt_text(config: dict[str, Any] | None = None) -> str:
    phase_prompt = _phase_balance_prompt(config)
    return """# OB11 ZBrush Body Cut LLM 剪辑任务

你是一个熟悉 ZBrush、OB11 头壳、小红书缩时视频节奏的剪辑顾问。

请根据 overview_contact_sheet.jpg、node_contact_sheet_01.jpg、
high_detail_contact_sheet.jpg、frame_manifest.json 和 operation_candidates.csv，
输出严格 JSON 格式的 edit_decision.json。

注意：
- 你不能知道真实 ZBrush 命令，不要编造真实笔刷名称。
- 只根据画面判断视觉阶段和剪辑价值。
- 只负责雕刻过程 body cut，不选择或生成 Blender hook。
- 输入分析基础视频默认已经是原始录屏的 5 倍速，不要把它误当作原始时间。
- body cut 第 0 秒直接进入雕刻过程，主发布版必须压缩到约 60 秒。
- 前 20 秒应有 2–3 个明显变化节点。

## 头发区域识别

先判断下列区域是否存在，并写入 hair_region_presence：
- front_hair（前发）：额头前方的刘海、前侧发束。
- sideburns（鬓发）：太阳穴、脸侧、耳侧的发束。
- back_hair（后发）：贴近头部后侧的主要后发体块。
- other_hair_blocks（其他发块）：主后发之外额外伸出的独立体块，例如马尾、
  麻花辫、双马尾等；画面中没有时必须标记为 false。

再识别每个存在区域的制作阶段：
- blockout（大型）：建立轮廓、体积、位置和主要形体。
- refinement（细化）：刻画发丝、沟槽、边缘、表面与清理细节。
- other：不属于上述两类的过程。

60 秒版本必须分别展示每个存在区域的 blockout 结果和 refinement 结果。
用于满足该要求的片段必须设置 include_in_body_60s=true、
shows_phase_result=true，并填写对应 hair_region 和 process_phase。

## 取舍与时长

- 先保证所有存在区域的大型和细化结果都被展示，再按 importance 从高到低选片段。
- 前发与鬓发细化、造型辨识度高的其他发块、明显完成节点优先。
- 重复修改、UI 操作、无结果的旋转缩放、长时间静止优先删除或压缩。
- importance 使用 0–10，10 表示最重要。
- 所有 include_in_body_60s=true 且未删除片段的 output_duration_seconds 总和应约为 60 秒。
- 如果证据包中存在 style_profile.yaml，必须优先参考其中的长期偏好。
{phase_prompt}

## 动作规则

- edit_action 只能使用：keep、keep_compress、keep_trim_to_candidate_range、
  keep_speedup_inside_candidate_range、delete、use_as_transition、
  keep_until_action_completion、keep_as_body_cut_end_state。
- keep_trim_to_candidate_range 表示保留候选范围；keep_speedup_inside_candidate_range
  表示保留候选范围并按照 output_duration_seconds 压缩加速。
- 任何其他 keep_* 动作会按保留处理；名称包含 speedup/compress 时按压缩保留，
  名称包含 transition 时按过渡处理。不要创造不以 keep_ 开头的未知动作。

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
  "hair_region_presence": {
    "front_hair": true,
    "sideburns": true,
    "back_hair": true,
    "other_hair_blocks": false
  },
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
requires_final_position、result_visible_at_next_node、hair_region、process_phase、
shows_phase_result、importance 和 reason。

hair_region 只能使用 front_hair、sideburns、back_hair、other_hair_blocks、
not_hair。process_phase 只能使用 blockout、refinement、other。
""".replace("{phase_prompt}", phase_prompt)


def _phase_balance_prompt(config: dict[str, Any] | None) -> str:
    config = config or {}
    llm_package = _section(config, "llm_package")
    if not bool(llm_package.get("phase_balance_enabled", False)):
        return ""
    blockout = max(0.1, float(llm_package.get("blockout_duration_weight", 1.0)))
    refinement = max(0.1, float(llm_package.get("refinement_duration_weight", 2.0)))
    total = blockout + refinement
    target = _body_60_target_seconds(config)
    blockout_seconds = target * blockout / total
    refinement_seconds = target * refinement / total
    return (
        "\n### 手动阶段比例要求\n\n"
        f"- 本次必须按 大型:细化 = {blockout:.2f}:{refinement:.2f} 分配 60 秒主体时长。\n"
        f"- blockout 阶段总输出时长约 {blockout_seconds:.1f} 秒。\n"
        f"- refinement 阶段总输出时长约 {refinement_seconds:.1f} 秒。\n"
        "- 如果必须保留过渡或 other 片段，只保留极短必要时间，并优先从低 importance 内容中扣减。\n"
        "- 生成 edit_decision.json 时直接按这个比例设置各 segment 的 output_duration_seconds。\n"
    )


def _body_60_target_seconds(config: dict[str, Any]) -> float:
    versions = _section(config, "cut_versions")
    body_60 = versions.get("body_60s", {})
    if not isinstance(body_60, dict):
        return 60.0
    return max(1.0, float(body_60.get("target_duration_seconds", 60)))
