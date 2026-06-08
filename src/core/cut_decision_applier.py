from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol


class CommandRunner(Protocol):
    def run(self, command: list[str]) -> None:
        pass


@dataclass(frozen=True)
class CutDecision:
    node_id: str
    label: str
    start_global_time: float
    end_global_time: float
    duration_seconds: float
    confidence: float
    keep_in_body_45s: bool
    keep_in_body_60s: bool
    keep_in_body_120s: bool
    speed_multiplier: float
    reason: str
    human_note: str

    @property
    def output_duration_seconds(self) -> float:
        return max(0.0, self.end_global_time - self.start_global_time) / max(
            self.speed_multiplier,
            0.001,
        )


def read_cut_decisions(path: Path) -> list[CutDecision]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [_row_to_decision(row) for row in rows]


def select_segments(
    decisions: list[CutDecision],
    version: str,
    target_duration_seconds: float | None = None,
) -> list[CutDecision]:
    flag = f"keep_in_{version}"
    selected = [
        item
        for item in decisions
        if bool(getattr(item, flag, False))
        and item.end_global_time > item.start_global_time
    ]
    selected.sort(key=lambda item: item.start_global_time)
    if target_duration_seconds is None or target_duration_seconds <= 0:
        return selected
    return _limit_to_target(selected, target_duration_seconds)


class CutDecisionApplier:
    def __init__(self, runner: CommandRunner, pixel_format: str = "yuv420p") -> None:
        self.runner = runner
        self.pixel_format = pixel_format

    def create_cut(self, source: Path, output: Path, segments: list[CutDecision]) -> None:
        if not segments:
            raise ValueError("没有可导出的剪辑片段")
        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-filter_complex",
                _filter_complex(segments),
                "-map",
                "[outv]",
                "-c:v",
                "libx264",
                "-pix_fmt",
                self.pixel_format,
                "-an",
                str(output),
            ]
        )


def _row_to_decision(row: dict[str, str]) -> CutDecision:
    start = _float(row.get("start_global_time"), 0.0)
    end = _float(row.get("end_global_time"), start)
    return CutDecision(
        node_id=row.get("node_id", ""),
        label=row.get("label", ""),
        start_global_time=start,
        end_global_time=end,
        duration_seconds=_float(row.get("duration_seconds"), max(0.0, end - start)),
        confidence=_float(row.get("confidence"), 0.0),
        keep_in_body_45s=_bool(row.get("keep_in_body_45s")),
        keep_in_body_60s=_bool(row.get("keep_in_body_60s")),
        keep_in_body_120s=_bool(row.get("keep_in_body_120s")),
        speed_multiplier=max(0.001, _float(row.get("speed_multiplier"), 1.0)),
        reason=row.get("reason", ""),
        human_note=row.get("human_note", ""),
    )


def _limit_to_target(
    selected: list[CutDecision],
    target_duration_seconds: float,
) -> list[CutDecision]:
    limited: list[CutDecision] = []
    used = 0.0
    for segment in selected:
        remaining = target_duration_seconds - used
        if remaining <= 0:
            break
        duration = segment.output_duration_seconds
        if duration <= remaining:
            limited.append(segment)
            used += duration
            continue
        trimmed_end = segment.start_global_time + (remaining * segment.speed_multiplier)
        limited.append(
            replace(
                segment,
                end_global_time=round(trimmed_end, 3),
                duration_seconds=round(max(0.0, trimmed_end - segment.start_global_time), 3),
            )
        )
        break
    return limited


def _filter_complex(segments: list[CutDecision]) -> str:
    trims: list[str] = []
    labels: list[str] = []
    for index, segment in enumerate(segments):
        label = f"v{index}"
        labels.append(f"[{label}]")
        trims.append(
            (
                f"[0:v]trim=start={segment.start_global_time:.3f}:"
                f"end={segment.end_global_time:.3f},"
                f"setpts=(PTS-STARTPTS)/{segment.speed_multiplier:.3f}[{label}]"
            )
        )
    return ";".join(trims + [f"{''.join(labels)}concat=n={len(segments)}:v=1:a=0[outv]"])


def _float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}
