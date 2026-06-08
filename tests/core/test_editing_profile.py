from __future__ import annotations

import json
import zipfile
from pathlib import Path

import yaml

from src.core.editing_profile import EditingProfileManager


def _decision(blockout_duration: float, refinement_duration: float) -> dict:
    return {
        "video_type": "body_cut_only",
        "recommended_body_duration_seconds": 60,
        "segments": [
            {
                "node_id": "node_0001",
                "edit_action": "keep",
                "include_in_body_60s": True,
                "output_duration_seconds": blockout_duration,
                "hair_region": "front_hair",
                "process_phase": "blockout",
                "importance": 8,
            },
            {
                "node_id": "node_0002",
                "edit_action": "keep",
                "include_in_body_60s": True,
                "output_duration_seconds": refinement_duration,
                "hair_region": "front_hair",
                "process_phase": "refinement",
                "importance": 10,
            },
        ],
    }


def test_editing_profile_records_confirmed_decision_feedback(tmp_path: Path) -> None:
    generated = tmp_path / "generated.json"
    final = tmp_path / "final.json"
    generated.write_text(json.dumps(_decision(50, 10)), encoding="utf-8")
    final.write_text(json.dumps(_decision(20, 40)), encoding="utf-8")

    result = EditingProfileManager(tmp_path / "profile").confirm_decision(
        generated,
        final,
        project_name="demo",
    )

    assert result.sample_count == 1
    assert result.diff["duration_changed_nodes"] == ["node_0001", "node_0002"]
    profile = yaml.safe_load((tmp_path / "profile" / "style_profile.yaml").read_text(encoding="utf-8"))
    assert profile["sample_count"] == 1
    assert profile["phase_ratio"] == {"blockout": 1.0, "refinement": 2.0}
    assert profile["phase_duration_seconds"] == {"blockout": 20.0, "refinement": 40.0}
    assert profile["region_phase_priority"]["front_hair/refinement"] == 10.0
    log_lines = (tmp_path / "profile" / "feedback_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 1
    feedback = json.loads(log_lines[0])
    assert feedback["project_name"] == "demo"
    assert feedback["generated_summary"]["selected_duration_seconds"] == 60.0
    assert feedback["final_summary"]["segments"][0]["node_id"] == "node_0001"


def test_editing_profile_snapshot_export_and_import(tmp_path: Path) -> None:
    manager = EditingProfileManager(tmp_path / "profile")
    manager.save_profile(
        {
            "version": 1,
            "sample_count": 3,
            "phase_ratio": {"blockout": 1.0, "refinement": 2.0},
        }
    )

    snapshot = manager.snapshot_to(tmp_path / "package" / "style_profile.yaml")
    archive = manager.export_archive(tmp_path / "profile.zip")
    imported = EditingProfileManager(tmp_path / "imported")
    imported.import_archive(archive)

    assert snapshot.exists()
    assert zipfile.is_zipfile(archive)
    assert imported.load_profile()["sample_count"] == 3
