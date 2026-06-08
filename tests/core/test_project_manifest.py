from __future__ import annotations

import csv
import json
from pathlib import Path

from src.core.project_manifest import ProjectManifest


def test_project_manifest_collects_outputs_timeline_nodes_and_warnings(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "full_concat.mp4").write_bytes(b"video")
    (output / "body_cut_60s.mp4").write_bytes(b"video")
    (output / "edit_report.json").write_text(
        json.dumps(
            {
                "timeline": [{"source_file": "part1.mp4", "global_start": 0.0}],
                "warnings": ["order_conflict"],
            }
        ),
        encoding="utf-8",
    )
    with (output / "cut_decision.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["node_id", "keep_in_body_60s"],
        )
        writer.writeheader()
        writer.writerows(
            [
                {"node_id": "node_0001", "keep_in_body_60s": "true"},
                {"node_id": "node_0002", "keep_in_body_60s": "false"},
            ]
        )

    path = ProjectManifest(tmp_path, {"project": {"name": "demo"}}).refresh(
        source_files=["part1.mp4"],
        input_order=["part1.mp4"],
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["project_name"] == "demo"
    assert payload["created_at"]
    assert payload["source_files"] == ["part1.mp4"]
    assert payload["input_order"] == ["part1.mp4"]
    assert payload["paths"]["full_concat"] == "output/full_concat.mp4"
    assert payload["paths"]["body_cut_60s"] == "output/body_cut_60s.mp4"
    assert payload["paths"]["body_cut_45s"] is None
    assert payload["global_timeline_map"][0]["source_file"] == "part1.mp4"
    assert payload["selected_nodes"] == ["node_0001"]
    assert payload["deleted_nodes"] == ["node_0002"]
    assert payload["warnings"] == ["order_conflict"]


def test_project_manifest_preserves_created_at_across_refreshes(tmp_path: Path) -> None:
    manifest = ProjectManifest(tmp_path, {})

    path = manifest.refresh()
    first = json.loads(path.read_text(encoding="utf-8"))["created_at"]
    manifest.refresh()
    second = json.loads(path.read_text(encoding="utf-8"))["created_at"]

    assert second == first
