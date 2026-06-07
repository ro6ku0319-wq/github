from __future__ import annotations

import csv
import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.core.cut_decision_applier import CommandRunner, CutDecision, CutDecisionApplier
from src.core.ffmpeg_runner import FFmpegRunner
from src.core.llm_decision_schema import (
    normalise_edit_action,
    normalise_node_id,
    validate_llm_decision,
)
from src.core.timecode import format_timecode, parse_timecode
from src.core.project_manifest import ProjectManifest


@dataclass(frozen=True)
class LlmDecisionResult:
    output_video: Path
    report_path: Path
    marker_path: Path
    warnings: list[str]


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class LlmDecisionPipeline:
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

    def apply(self, decision_path: Path) -> LlmDecisionResult:
        source = self.output_dir / "accelerated_base.mp4"
        candidates_path = self.output_dir / "cut_decision.csv"
        if not source.exists():
            raise FileNotFoundError(f"缺少 {source.name}，请先运行基础处理")
        if not candidates_path.exists():
            raise FileNotFoundError(f"缺少 {candidates_path.name}，请先运行节点分析")
        decision_path = Path(decision_path)
        if not decision_path.is_absolute():
            decision_path = (self.project_dir / decision_path).resolve()
        if not decision_path.exists():
            raise FileNotFoundError(f"找不到 edit_decision.json: {decision_path}")

        self._update(10, "校验 edit_decision.json")
        payload = json.loads(decision_path.read_text(encoding="utf-8"))
        known = self._known_node_ids(candidates_path)
        validation = validate_llm_decision(payload, known)
        for warning in validation.warnings:
            self.log(warning)
        segments = _segments_to_decisions(validation.payload["segments"])
        if not segments:
            raise ValueError("edit_decision.json 没有可保留的 segments")

        result_dir = self.output_dir / "llm_result"
        result_dir.mkdir(parents=True, exist_ok=True)
        saved_decision = result_dir / "edit_decision.json"
        if decision_path.resolve() != saved_decision.resolve():
            shutil.copy2(decision_path, saved_decision)
        output_video = result_dir / "llm_guided_body_cut.mp4"
        self._update(45, "生成 llm_guided_body_cut.mp4")
        self.applier.create_cut(source, output_video, segments)

        report = result_dir / "llm_edit_report.txt"
        marker_path = result_dir / "davinci_markers.csv"
        self._update(85, "生成 LLM 报告和 markers")
        _write_report(report, validation.payload, segments, validation.warnings)
        _write_llm_markers(marker_path, validation.payload.get("davinci_markers", []))
        ProjectManifest(self.project_dir, self.config).refresh()
        self._update(100, "应用 LLM 剪辑说明书完成")
        return LlmDecisionResult(
            output_video=output_video,
            report_path=report,
            marker_path=marker_path,
            warnings=validation.warnings,
        )

    @staticmethod
    def _known_node_ids(path: Path) -> set[str]:
        with path.open(encoding="utf-8", newline="") as handle:
            return {
                normalise_node_id(row.get("node_id", ""))
                for row in csv.DictReader(handle)
            }

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)


def _segments_to_decisions(segments: list[dict[str, Any]]) -> list[CutDecision]:
    decisions: list[CutDecision] = []
    for segment in segments:
        action = normalise_edit_action(segment["edit_action"])
        if action == "delete":
            continue
        start = parse_timecode(segment["start_global_time"])
        end = parse_timecode(segment["end_global_time"])
        output_duration = float(segment["output_duration_seconds"])
        speed = float(segment["speed_multiplier"])
        if action == "keep_compress" and output_duration > 0:
            speed = (end - start) / output_duration
        elif action == "use_as_transition":
            end = min(end, start + max(0.25, min(1.0, output_duration or 1.0)))
        decisions.append(
            CutDecision(
                node_id=normalise_node_id(segment["node_id"]),
                label=str(segment["label"]),
                start_global_time=start,
                end_global_time=end,
                duration_seconds=end - start,
                confidence=1.0,
                keep_in_body_45s=bool(segment["include_in_body_45s"]),
                keep_in_body_60s=bool(segment["include_in_body_60s"]),
                keep_in_body_120s=bool(segment["include_in_body_120s"]),
                speed_multiplier=max(0.1, min(100.0, speed)),
                reason=str(segment["reason"]),
                human_note=str(segment.get("label_cn", "")),
            )
        )
    return decisions


def _write_report(
    path: Path,
    payload: dict[str, Any],
    segments: list[CutDecision],
    warnings: list[str],
) -> None:
    lines = [
        "OB11 ZBrush Body Cut LLM 剪辑报告",
        "",
        f"video_type: {payload.get('video_type')}",
        f"recommended_body_duration_seconds: {payload.get('recommended_body_duration_seconds')}",
        "",
        "保留片段:",
    ]
    lines.extend(
        (
            f"- {item.node_id} {item.label}: "
            f"{format_timecode(item.start_global_time)} -> {format_timecode(item.end_global_time)}, "
            f"speed={item.speed_multiplier:.3f}, reason={item.reason}"
        )
        for item in segments
    )
    lines.extend(["", "警告:"])
    lines.extend(f"- {warning}" for warning in warnings or ["无"])
    lines.extend(["", "给人工剪辑师的备注:"])
    notes = payload.get("notes_for_human_editor", [])
    lines.extend(f"- {note}" for note in notes or ["无"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_llm_markers(path: Path, markers: object) -> None:
    fieldnames = [
        "marker_time",
        "name",
        "note",
        "source_global_time",
        "source_file",
        "source_timecode",
        "node_id",
        "label",
    ]
    rows = markers if isinstance(markers, list) else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for marker in rows:
            if not isinstance(marker, dict):
                continue
            writer.writerow(
                {
                    "marker_time": marker.get("time", ""),
                    "name": marker.get("name", ""),
                    "note": marker.get("note", ""),
                    "source_global_time": marker.get("source_global_time", ""),
                    "source_file": marker.get("source_file", ""),
                    "source_timecode": marker.get("source_timecode", ""),
                    "node_id": marker.get("node_id", ""),
                    "label": marker.get("label", ""),
                }
            )
