from __future__ import annotations

import csv
import json
from pathlib import Path

from tests.core.test_llm_decision_pipeline import decision_payload
from src.core.codex_decision_pipeline import CodexDecisionPipeline


class FakeCodexRunner:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> None:
        self.commands.append(command)
        output_path = Path(command[command.index("-o") + 1])
        output_path.write_text(json.dumps(self.payload), encoding="utf-8")


def _write_package(output: Path) -> None:
    package = output / "llm_review_package"
    package.mkdir(parents=True)
    for name in (
        "overview_contact_sheet.jpg",
        "node_contact_sheet_01.jpg",
        "high_detail_contact_sheet.jpg",
    ):
        (package / name).write_bytes(b"image")
    (package / "frame_manifest.json").write_text('{"frames":[]}', encoding="utf-8")
    (package / "operation_candidates.csv").write_text("node_id\nnode_0001\n", encoding="utf-8")
    (package / "llm_prompt.md").write_text("prompt", encoding="utf-8")
    with (output / "cut_decision.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["node_id"])
        writer.writeheader()
        writer.writerows([{"node_id": "node_0001"}, {"node_id": "node_0002"}])


def test_codex_decision_pipeline_generates_review_json_and_backup(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    _write_package(output)
    existing = output / "llm_result" / "edit_decision.json"
    existing.parent.mkdir()
    existing.write_text('{"old": true}', encoding="utf-8")
    runner = FakeCodexRunner(decision_payload())

    result = CodexDecisionPipeline(
        tmp_path,
        {"output": {"output_dir": "output"}},
        runner=runner,
        profile_dir=tmp_path / "profile",
    ).generate()

    command = runner.commands[0]
    assert command[:3] == ["codex.cmd", "exec", "--ephemeral"]
    assert "--sandbox" in command
    assert "read-only" in command
    assert "--output-schema" in command
    assert command.count("--image") == 3
    assert command[-2] == "--"
    assert "$bodycut-editor" in " ".join(command)
    assert result.generated_path == output / "llm_result" / "codex_generated_edit_decision.json"
    assert result.review_path == output / "llm_result" / "edit_decision.json"
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert json.loads(result.review_path.read_text(encoding="utf-8"))["video_type"] == "body_cut_only"
    assert (output / "llm_review_package" / "style_profile.yaml").exists()
    assert (output / "llm_review_package" / "edit_decision.schema.json").exists()
    schema = json.loads((output / "llm_review_package" / "edit_decision.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) <= set(schema["properties"])
    assert set(schema["properties"]["segments"]["items"]["required"]) <= set(
        schema["properties"]["segments"]["items"]["properties"]
    )
