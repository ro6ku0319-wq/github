from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.report_writer import write_json


OUTPUT_PATHS = {
    "full_concat": "full_concat.mp4",
    "accelerated_base": "accelerated_base.mp4",
    "body_cut_45s": "body_cut_45s.mp4",
    "body_cut_60s": "body_cut_60s.mp4",
    "body_cut_120s": "body_cut_120s.mp4",
    "auto_node_preview": "auto_node_preview.mp4",
    "llm_guided_body_cut": "llm_result/llm_guided_body_cut.mp4",
    "external_hook": "normalized_hook.mp4",
    "final_with_hook_45s": "final_with_hook_45s.mp4",
    "final_with_hook_60s": "final_with_hook_60s.mp4",
    "final_with_hook_120s": "final_with_hook_120s.mp4",
    "cut_decision": "cut_decision.csv",
    "node_contact_sheet": "node_contact_sheet.jpg",
    "activity_curve": "activity_curve.png",
    "llm_package": "llm_review_package",
}


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class ProjectManifest:
    def __init__(self, project_dir: Path, config: dict[str, Any]) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config = config

    @property
    def output_dir(self) -> Path:
        output = _section(self.config, "output")
        return (self.project_dir / str(output.get("output_dir", "output"))).resolve()

    @property
    def path(self) -> Path:
        return self.output_dir / "project_manifest.json"

    def refresh(
        self,
        source_files: list[str] | None = None,
        input_order: list[str] | None = None,
    ) -> Path:
        previous = self._read_json(self.path)
        edit_report = self._read_json(self.output_dir / "edit_report.json")
        selected, deleted = self._read_nodes(self.output_dir / "cut_decision.csv")
        payload = {
            "project_name": _section(self.config, "project").get(
                "name",
                self.project_dir.name,
            ),
            "created_at": previous.get("created_at")
            or datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source_files": source_files
            if source_files is not None
            else previous.get("source_files", []),
            "input_order": input_order
            if input_order is not None
            else previous.get("input_order", []),
            "paths": {
                key: self._relative_if_exists(self.output_dir / value)
                for key, value in OUTPUT_PATHS.items()
            },
            "global_timeline_map": edit_report.get(
                "timeline",
                previous.get("global_timeline_map", []),
            ),
            "selected_nodes": selected,
            "deleted_nodes": deleted,
            "warnings": edit_report.get("warnings", previous.get("warnings", [])),
        }
        write_json(self.path, payload)
        return self.path

    def _relative_if_exists(self, path: Path) -> str | None:
        if not path.exists():
            return None
        try:
            return path.resolve().relative_to(self.project_dir).as_posix()
        except ValueError:
            return str(path.resolve())

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _read_nodes(path: Path) -> tuple[list[str], list[str]]:
        if not path.exists():
            return [], []
        selected: list[str] = []
        deleted: list[str] = []
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                node_id = str(row.get("node_id", "")).strip()
                if not node_id:
                    continue
                keep = any(
                    str(row.get(field, "")).strip().lower() in {"true", "1", "yes"}
                    for field in (
                        "keep_in_body_45s",
                        "keep_in_body_60s",
                        "keep_in_body_120s",
                    )
                )
                (selected if keep else deleted).append(node_id)
        return selected, deleted
