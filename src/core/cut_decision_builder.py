from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.core.coarse_segmenter import NodeCandidate


CUT_DECISION_FIELDS = [
    "node_id",
    "label",
    "start_global_time",
    "end_global_time",
    "duration_seconds",
    "confidence",
    "keep_in_body_45s",
    "keep_in_body_60s",
    "keep_in_body_120s",
    "speed_multiplier",
    "reason",
    "human_note",
    "action_start_frame",
    "action_peak_frame",
    "action_completion_frame",
    "cut_after_frame",
    "undo_redo_confidence",
    "reverted_to_previous_state",
    "keep_successful_redo_only",
]


OPERATION_SCORE_FIELDS = [
    "sample_id",
    "time_seconds",
    "brightness",
    "edge_density",
    "diff_score",
    "edge_diff_score",
    "region_change_score",
    "activity_score",
    "black_frame",
    "global_diff_score",
    "center_diff_score",
    "ui_diff_score",
    "local_change_density",
    "brightness_score",
    "detail_score",
    "stability_after_change",
    "novelty_score",
    "repetition_score",
    "reverted_to_previous_state",
]


def build_cut_decision_rows(
    candidates: list[NodeCandidate],
    operation_priority: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    priority = operation_priority or {}
    rows: list[dict[str, str]] = []
    for candidate in candidates:
        label_priority = float(priority.get(candidate.label, 5))
        weighted_score = candidate.confidence + (label_priority / 20.0)
        rows.append(
            {
                "node_id": candidate.node_id,
                "label": candidate.label,
                "start_global_time": f"{candidate.start_global_time:.3f}",
                "end_global_time": f"{candidate.end_global_time:.3f}",
                "duration_seconds": f"{candidate.duration_seconds:.3f}",
                "confidence": f"{candidate.confidence:.3f}",
                "keep_in_body_45s": _bool_text(weighted_score >= 0.72),
                "keep_in_body_60s": _bool_text(weighted_score >= 0.55),
                "keep_in_body_120s": _bool_text(weighted_score >= 0.35),
                "speed_multiplier": "1.000",
                "reason": candidate.reason,
                "human_note": "",
                "action_start_frame": str(candidate.action_start_frame),
                "action_peak_frame": str(candidate.action_peak_frame),
                "action_completion_frame": str(candidate.action_completion_frame),
                "cut_after_frame": str(candidate.cut_after_frame),
                "undo_redo_confidence": f"{candidate.undo_redo_confidence:.3f}",
                "reverted_to_previous_state": _bool_text(
                    candidate.reverted_to_previous_state
                ),
                "keep_successful_redo_only": _bool_text(
                    candidate.keep_successful_redo_only
                ),
            }
        )
    return rows


def write_cut_decision_csv(path: Path, rows: list[dict[str, str]]) -> None:
    _write_dict_csv(path, CUT_DECISION_FIELDS, rows)


def write_operation_score_table_csv(path: Path, rows: list[dict[str, str]]) -> None:
    _write_dict_csv(path, OPERATION_SCORE_FIELDS, rows)


def _write_dict_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
