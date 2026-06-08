from __future__ import annotations

import json
from pathlib import Path

from tests.core.test_llm_decision_pipeline import decision_payload
from src.core.llm_decision_editor import (
    editable_rows_from_payload,
    payload_from_editable_rows,
    read_decision_payload,
    write_decision_payload,
)


def test_llm_decision_editor_round_trips_editable_segment_fields(tmp_path: Path) -> None:
    payload = decision_payload()
    rows = editable_rows_from_payload(payload)
    rows[0]["edit_action"] = "delete"
    rows[1]["output_duration_seconds"] = "12.5"
    rows[1]["importance"] = "7"

    updated = payload_from_editable_rows(payload, rows)

    assert updated["segments"][0]["edit_action"] == "delete"
    assert updated["segments"][1]["output_duration_seconds"] == 12.5
    assert updated["segments"][1]["importance"] == 7.0

    path = tmp_path / "edit_decision.json"
    write_decision_payload(path, updated)
    assert read_decision_payload(path)["segments"][1]["importance"] == 7.0
    assert json.loads(path.read_text(encoding="utf-8"))["segments"][0]["edit_action"] == "delete"
