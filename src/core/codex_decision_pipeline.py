from __future__ import annotations

import csv
import json
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from src.core.editing_profile import EditingProfileManager
from src.core.llm_decision_schema import normalise_node_id, validate_llm_decision
from src.core.project_manifest import ProjectManifest


class CodexRunner(Protocol):
    def run(self, command: list[str]) -> None:
        pass


class SubprocessCodexRunner:
    def run(self, command: list[str]) -> None:
        subprocess.run(command, check=True)


@dataclass(frozen=True)
class CodexDecisionResult:
    generated_path: Path
    review_path: Path
    schema_path: Path
    backup_path: Path | None


class CodexDecisionPipeline:
    def __init__(
        self,
        project_dir: Path,
        config: dict,
        log: Callable[[str], None] | None = None,
        progress: Callable[[int, str], None] | None = None,
        runner: CodexRunner | None = None,
        profile_dir: Path | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config = config
        self.log = log or (lambda message: None)
        self.progress = progress or (lambda value, message: None)
        self.runner = runner or SubprocessCodexRunner()
        self.profile = EditingProfileManager(profile_dir)

    @property
    def output_dir(self) -> Path:
        output = self.config.get("output", {})
        if not isinstance(output, dict):
            output = {}
        return (self.project_dir / str(output.get("output_dir", "output"))).resolve()

    @property
    def package_dir(self) -> Path:
        return self.output_dir / "llm_review_package"

    def generate(self) -> CodexDecisionResult:
        self._require_package()
        result_dir = self.output_dir / "llm_result"
        result_dir.mkdir(parents=True, exist_ok=True)
        generated_path = result_dir / "codex_generated_edit_decision.json"
        review_path = result_dir / "edit_decision.json"
        self._update(10, "准备 Codex 选片证据包")
        self.profile.snapshot_to(self.package_dir / "style_profile.yaml")
        schema_path = self.package_dir / "edit_decision.schema.json"
        schema_path.write_text(
            json.dumps(_edit_decision_schema(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_output = result_dir / "codex_exec_output.json"
        self._update(30, "调用 Codex 生成 edit_decision.json")
        self.runner.run(self._command(schema_path, temporary_output))
        payload = json.loads(temporary_output.read_text(encoding="utf-8"))
        validate_llm_decision(payload, self._known_node_ids())
        generated_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        backup_path = _backup_existing(review_path)
        shutil.copy2(generated_path, review_path)
        ProjectManifest(self.project_dir, self.config).refresh()
        self._update(100, "Codex 剪辑说明书生成完成")
        return CodexDecisionResult(
            generated_path=generated_path,
            review_path=review_path,
            schema_path=schema_path,
            backup_path=backup_path,
        )

    def _command(self, schema_path: Path, output_path: Path) -> list[str]:
        images = [
            self.package_dir / "overview_contact_sheet.jpg",
            self.package_dir / "node_contact_sheet_01.jpg",
            self.package_dir / "high_detail_contact_sheet.jpg",
        ]
        command = [
            "codex.cmd",
            "exec",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--cd",
            str(self.project_dir),
            "--output-schema",
            str(schema_path),
            "-o",
            str(output_path),
        ]
        for image in images:
            command.extend(["--image", str(image)])
        command.append(_codex_prompt(self.package_dir))
        return command

    def _known_node_ids(self) -> set[str]:
        with (self.output_dir / "cut_decision.csv").open(
            encoding="utf-8",
            newline="",
        ) as handle:
            return {
                normalise_node_id(row.get("node_id", ""))
                for row in csv.DictReader(handle)
            }

    def _require_package(self) -> None:
        required = [
            self.package_dir / "overview_contact_sheet.jpg",
            self.package_dir / "node_contact_sheet_01.jpg",
            self.package_dir / "high_detail_contact_sheet.jpg",
            self.package_dir / "frame_manifest.json",
            self.package_dir / "operation_candidates.csv",
            self.package_dir / "llm_prompt.md",
            self.output_dir / "cut_decision.csv",
        ]
        missing = [path.name for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("缺少 Codex 证据包文件: " + ", ".join(missing))

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)


def _backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.{timestamp}.bak{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def _codex_prompt(package_dir: Path) -> str:
    return (
        "$bodycut-editor\n"
        "读取以下 OB11 ZBrush body cut 证据包，严格输出符合 schema 的 edit_decision.json。"
        "不要解释，不要 Markdown。\n"
        f"证据包目录: {package_dir}\n"
        "必须参考 llm_prompt.md、operation_candidates.csv、frame_manifest.json、"
        "style_profile.yaml 和三张联系图。"
    )


def _edit_decision_schema() -> dict:
    segment_required = [
        "node_id",
        "label",
        "label_cn",
        "start_global_time",
        "end_global_time",
        "edit_action",
        "include_in_body_45s",
        "include_in_body_60s",
        "include_in_body_120s",
        "output_duration_seconds",
        "speed_multiplier",
        "rhythm_role",
        "requires_final_position",
        "result_visible_at_next_node",
        "hair_region",
        "process_phase",
        "shows_phase_result",
        "importance",
        "reason",
    ]
    return {
        "type": "object",
        "additionalProperties": True,
        "required": [
            "video_type",
            "external_hook",
            "recommended_body_duration_seconds",
            "first_20_seconds_body_plan",
            "segments",
            "cover_candidates",
            "davinci_markers",
            "notes_for_human_editor",
        ],
        "properties": {
            "video_type": {"const": "body_cut_only"},
            "recommended_body_duration_seconds": {"type": "number"},
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": segment_required,
                },
            },
        },
    }
