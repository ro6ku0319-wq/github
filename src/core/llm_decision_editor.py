from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


EDITABLE_FIELDS = [
    "node_id",
    "label",
    "label_cn",
    "edit_action",
    "include_in_body_60s",
    "output_duration_seconds",
    "hair_region",
    "process_phase",
    "importance",
    "reason",
]

NUMERIC_FIELDS = {"output_duration_seconds", "importance"}
BOOLEAN_FIELDS = {"include_in_body_60s"}


def read_decision_payload(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("edit_decision.json 顶层必须是对象")
    return value


def write_decision_payload(path: Path, payload: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def editable_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for segment in payload.get("segments", []):
        if not isinstance(segment, dict):
            continue
        row: dict[str, str] = {}
        for field in EDITABLE_FIELDS:
            value = segment.get(field, "")
            if isinstance(value, bool):
                row[field] = "true" if value else "false"
            else:
                row[field] = str(value)
        rows.append(row)
    return rows


def payload_from_editable_rows(
    original_payload: dict[str, Any],
    rows: list[dict[str, object]],
) -> dict[str, Any]:
    payload = deepcopy(original_payload)
    segments = payload.get("segments", [])
    if not isinstance(segments, list):
        segments = []
    by_node = {
        str(row.get("node_id", "")): row
        for row in rows
        if str(row.get("node_id", ""))
    }
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        row = by_node.get(str(segment.get("node_id", "")))
        if row is None:
            continue
        for field in EDITABLE_FIELDS:
            if field in {"node_id", "label", "label_cn"} or field not in row:
                continue
            segment[field] = _coerce_field(field, row[field])
    payload["segments"] = segments
    return payload


def _coerce_field(field: str, value: object) -> object:
    if field in BOOLEAN_FIELDS:
        return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}
    if field in NUMERIC_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return str(value)
