from __future__ import annotations

import csv
from pathlib import Path

from src.core.cut_decision_applier import CutDecision


MARKER_FIELDS = [
    "node_id",
    "name",
    "start_seconds",
    "duration_seconds",
    "color",
    "description",
]


def write_davinci_markers_csv(path: Path, decisions: list[CutDecision]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MARKER_FIELDS)
        writer.writeheader()
        for decision in decisions:
            writer.writerow(
                {
                    "node_id": decision.node_id,
                    "name": f"{decision.node_id} {decision.label}",
                    "start_seconds": f"{decision.start_global_time:.3f}",
                    "duration_seconds": f"{decision.duration_seconds:.3f}",
                    "color": _color_for(decision),
                    "description": _description(decision),
                }
            )


def _color_for(decision: CutDecision) -> str:
    if decision.keep_in_body_45s:
        return "Green"
    if decision.keep_in_body_60s:
        return "Blue"
    if decision.keep_in_body_120s:
        return "Yellow"
    return "Grey"


def _description(decision: CutDecision) -> str:
    note = f" note={decision.human_note}" if decision.human_note else ""
    return f"confidence={decision.confidence:.3f}; reason={decision.reason}{note}"
