from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from src.core.llm_decision_pipeline import LlmDecisionPipeline, _segments_to_decisions
from src.core.llm_decision_schema import (
    LlmDecisionValidationError,
    normalise_edit_action,
    validate_llm_decision,
)


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> None:
        self.commands.append(command)


def decision_payload() -> dict:
    return {
        "video_type": "body_cut_only",
        "external_hook": {
            "provided_by_user": True,
            "generated_by": "Blender",
            "not_included_in_this_decision": True,
            "expected_duration_seconds": 2,
        },
        "recommended_body_duration_seconds": 60,
        "first_20_seconds_body_plan": [
            {
                "output_time_range": "00:00-00:10",
                "source_global_time": "00:00:01.0",
                "purpose": "快速进入雕刻",
                "reason": "明显变化",
            }
        ],
        "segments": [
            {
                "node_id": "node_0001",
                "label": "hair_detail",
                "label_cn": "发丝细节",
                "start_global_time": "00:00:01.0",
                "end_global_time": "00:00:05.0",
                "edit_action": "keep",
                "include_in_body_45s": True,
                "include_in_body_60s": True,
                "include_in_body_120s": True,
                "output_duration_seconds": 4,
                "speed_multiplier": 1,
                "rhythm_role": "highlight",
                "requires_final_position": False,
                "result_visible_at_next_node": True,
                "reason": "可读变化",
            },
            {
                "node_id": "node_0002",
                "label": "zoom_pan_view",
                "label_cn": "视角过渡",
                "start_global_time": "00:00:05.0",
                "end_global_time": "00:00:09.0",
                "edit_action": "keep_compress",
                "include_in_body_45s": False,
                "include_in_body_60s": True,
                "include_in_body_120s": True,
                "output_duration_seconds": 2,
                "speed_multiplier": 1,
                "rhythm_role": "transition",
                "requires_final_position": False,
                "result_visible_at_next_node": True,
                "reason": "短过渡",
            },
        ],
        "cover_candidates": [],
        "davinci_markers": [{"time": "00:00:01.0", "name": "前发", "note": "重点"}],
        "notes_for_human_editor": ["检查结尾节奏"],
    }


def write_cut_decision(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "node_id,label,start_global_time,end_global_time,duration_seconds,confidence,"
        "keep_in_body_45s,keep_in_body_60s,keep_in_body_120s,speed_multiplier,"
        "reason,human_note\n"
        "node_0001,hair_detail,1.000,5.000,4.000,0.900,true,true,true,1.000,"
        "high change,\n"
        "node_0002,zoom_pan_view,5.000,9.000,4.000,0.600,false,true,true,1.000,"
        "transition,\n",
        encoding="utf-8",
    )


def test_validate_llm_decision_rejects_missing_required_fields() -> None:
    with pytest.raises(LlmDecisionValidationError, match="segments"):
        validate_llm_decision({"video_type": "body_cut_only"}, known_node_ids=set())


def test_validate_llm_decision_reports_non_fatal_warnings() -> None:
    payload = decision_payload()
    payload["video_type"] = "includes_hook"
    payload["first_20_seconds_body_plan"] = []
    payload["segments"][0]["node_id"] = "node_9999"
    payload["segments"][0]["speed_multiplier"] = 200

    result = validate_llm_decision(payload, known_node_ids={"node_0001"})

    text = "\n".join(result.warnings)
    assert "video_type" in text
    assert "first_20_seconds_body_plan" in text
    assert "node_9999" in text
    assert "speed_multiplier" in text


def test_validate_llm_decision_rejects_string_boolean_fields() -> None:
    payload = decision_payload()
    payload["segments"][0]["include_in_body_45s"] = "false"

    with pytest.raises(LlmDecisionValidationError, match="include_in_body_45s"):
        validate_llm_decision(payload, known_node_ids={"node_0001", "node_0002"})


def test_validate_llm_decision_accepts_keep_trim_to_candidate_range() -> None:
    payload = decision_payload()
    payload["segments"][0]["edit_action"] = "keep_trim_to_candidate_range"

    result = validate_llm_decision(
        payload,
        known_node_ids={"node_0001", "node_0002"},
    )

    assert result.payload["segments"][0]["edit_action"] == "keep_trim_to_candidate_range"


def test_keep_speedup_inside_candidate_range_maps_to_compressed_keep() -> None:
    payload = decision_payload()
    segment = payload["segments"][0]
    segment["edit_action"] = "keep_speedup_inside_candidate_range"
    segment["output_duration_seconds"] = 2

    result = validate_llm_decision(
        payload,
        known_node_ids={"node_0001", "node_0002"},
    )
    decisions = _segments_to_decisions(result.payload["segments"])

    assert normalise_edit_action("keep_speedup_inside_candidate_range") == "keep_compress"
    assert decisions[0].speed_multiplier == 2.0


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("keep_trim_to_candidate_range", "keep"),
        ("keep_candidate_range", "keep"),
        ("trim_to_candidate_range", "keep"),
        ("keep_speedup_inside_candidate_range", "keep_compress"),
        ("speedup_inside_candidate_range", "keep_compress"),
        ("keep_as_transition", "use_as_transition"),
    ],
)
def test_llm_action_aliases_are_normalised(alias: str, canonical: str) -> None:
    assert normalise_edit_action(alias) == canonical


def test_llm_decision_pipeline_renders_guided_cut_report_and_markers(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output"
    source = output / "accelerated_base.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"placeholder")
    write_cut_decision(output / "cut_decision.csv")
    decision_path = output / "llm_result" / "edit_decision.json"
    decision_path.parent.mkdir(parents=True)
    decision_path.write_text(json.dumps(decision_payload()), encoding="utf-8")
    runner = FakeRunner()

    result = LlmDecisionPipeline(
        tmp_path,
        {"output": {"output_dir": "output"}},
        runner=runner,
    ).apply(decision_path)

    assert result.output_video == output / "llm_result" / "llm_guided_body_cut.mp4"
    assert (output / "llm_result" / "edit_decision.json").exists()
    assert len(runner.commands) == 1
    command = " ".join(runner.commands[0])
    assert "trim=start=1.000:end=5.000" in command
    assert "setpts=(PTS-STARTPTS)/2.000" in command
    assert "llm_guided_body_cut.mp4" in command
    report = (output / "llm_result" / "llm_edit_report.txt").read_text(encoding="utf-8")
    assert "node_0001" in report
    assert "检查结尾节奏" in report
    markers = list(
        csv.DictReader(
            (output / "llm_result" / "davinci_markers.csv").open(encoding="utf-8")
        )
    )
    assert markers[0]["name"] == "前发"
