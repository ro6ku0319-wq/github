from __future__ import annotations

import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.core.llm_decision_schema import normalise_edit_action, normalise_node_id


@dataclass(frozen=True)
class FeedbackResult:
    profile_path: Path
    feedback_log_path: Path
    sample_count: int
    diff: dict[str, Any]


def default_profile_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return root / "OB11BodyCut" / "editing_profile"


class EditingProfileManager:
    def __init__(self, profile_dir: Path | None = None) -> None:
        self.profile_dir = Path(profile_dir or default_profile_dir()).resolve()

    @property
    def profile_path(self) -> Path:
        return self.profile_dir / "style_profile.yaml"

    @property
    def feedback_log_path(self) -> Path:
        return self.profile_dir / "feedback_log.jsonl"

    def load_profile(self) -> dict[str, Any]:
        if not self.profile_path.exists():
            return _default_profile()
        value = yaml.safe_load(self.profile_path.read_text(encoding="utf-8"))
        return _merge_profile(value if isinstance(value, dict) else {})

    def save_profile(self, profile: dict[str, Any]) -> Path:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(
            yaml.safe_dump(profile, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return self.profile_path

    def snapshot_to(self, destination: Path) -> Path:
        self.save_profile(self.load_profile())
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.profile_path, destination)
        return destination

    def confirm_decision(
        self,
        generated_decision: Path,
        final_decision: Path,
        project_name: str,
    ) -> FeedbackResult:
        generated = _read_json(generated_decision)
        final = _read_json(final_decision)
        diff = _decision_diff(generated, final)
        final_stats = _decision_stats(final)
        profile = self.load_profile()
        sample_count = int(profile.get("sample_count", 0)) + 1
        profile["sample_count"] = sample_count
        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        profile["phase_ratio"] = final_stats["phase_ratio"]
        profile["phase_duration_seconds"] = final_stats["phase_duration_seconds"]
        profile["preferred_segment_duration"] = final_stats[
            "preferred_segment_duration"
        ]
        profile["region_phase_priority"] = final_stats["region_phase_priority"]
        self.save_profile(profile)
        self._append_feedback_log(
            {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "project_name": project_name,
                "generated_decision": str(Path(generated_decision).resolve()),
                "final_decision": str(Path(final_decision).resolve()),
                "generated_summary": _decision_summary(generated),
                "final_summary": _decision_summary(final),
                "diff": diff,
                "final_stats": final_stats,
            }
        )
        return FeedbackResult(
            profile_path=self.profile_path,
            feedback_log_path=self.feedback_log_path,
            sample_count=sample_count,
            diff=diff,
        )

    def export_archive(self, destination: Path) -> Path:
        self.save_profile(self.load_profile())
        destination = Path(destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(self.profile_path, "style_profile.yaml")
            if self.feedback_log_path.exists():
                archive.write(self.feedback_log_path, "feedback_log.jsonl")
        return destination

    def import_archive(self, source: Path) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(source) as archive:
            for name in ("style_profile.yaml", "feedback_log.jsonl"):
                try:
                    archive.extract(name, self.profile_dir)
                except KeyError:
                    continue

    def _append_feedback_log(self, payload: dict[str, Any]) -> None:
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        with self.feedback_log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _default_profile() -> dict[str, Any]:
    return {
        "version": 1,
        "sample_count": 0,
        "phase_ratio": {"blockout": 1.0, "refinement": 2.0},
        "phase_duration_seconds": {"blockout": 20.0, "refinement": 40.0},
        "preferred_segment_duration": {"blockout": 2.0, "refinement": 4.0},
        "region_phase_priority": {},
        "avoid": [
            "long_ui_operations",
            "repeated_rotation",
            "result_not_visible",
        ],
    }


def _merge_profile(value: dict[str, Any]) -> dict[str, Any]:
    merged = _default_profile()
    for key, item in value.items():
        if isinstance(item, dict) and isinstance(merged.get(key), dict):
            merged[key].update(item)
        else:
            merged[key] = item
    return merged


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _selected_segments(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    for segment in payload.get("segments", []):
        if not isinstance(segment, dict):
            continue
        node_id = normalise_node_id(segment.get("node_id", ""))
        if not node_id:
            continue
        if segment.get("include_in_body_60s") is not True:
            continue
        if normalise_edit_action(segment.get("edit_action", "")) == "delete":
            continue
        selected[node_id] = segment
    return selected


def _decision_diff(generated: dict[str, Any], final: dict[str, Any]) -> dict[str, Any]:
    generated_selected = _selected_segments(generated)
    final_selected = _selected_segments(final)
    generated_ids = set(generated_selected)
    final_ids = set(final_selected)
    changed_duration = sorted(
        node_id
        for node_id in generated_ids & final_ids
        if round(
            float(generated_selected[node_id].get("output_duration_seconds", 0.0)),
            3,
        )
        != round(float(final_selected[node_id].get("output_duration_seconds", 0.0)), 3)
    )
    return {
        "added_nodes": sorted(final_ids - generated_ids),
        "removed_nodes": sorted(generated_ids - final_ids),
        "duration_changed_nodes": changed_duration,
    }


def _decision_stats(payload: dict[str, Any]) -> dict[str, Any]:
    selected = list(_selected_segments(payload).values())
    phase_totals = {"blockout": 0.0, "refinement": 0.0}
    phase_counts = {"blockout": 0, "refinement": 0}
    priority: dict[str, list[float]] = {}
    for segment in selected:
        phase = str(segment.get("process_phase", "other"))
        if phase not in phase_totals:
            continue
        duration = float(segment.get("output_duration_seconds", 0.0))
        phase_totals[phase] += duration
        phase_counts[phase] += 1
        key = f"{segment.get('hair_region', 'not_hair')}/{phase}"
        priority.setdefault(key, []).append(float(segment.get("importance", 0.0)))
    blockout = phase_totals["blockout"]
    refinement = phase_totals["refinement"]
    if blockout > 0 and refinement > 0:
        base = min(blockout, refinement)
        ratio = {
            "blockout": round(blockout / base, 3),
            "refinement": round(refinement / base, 3),
        }
    else:
        ratio = {"blockout": 1.0, "refinement": 2.0}
    return {
        "phase_ratio": ratio,
        "phase_duration_seconds": {
            "blockout": round(blockout, 3),
            "refinement": round(refinement, 3),
        },
        "preferred_segment_duration": {
            phase: round(phase_totals[phase] / max(1, phase_counts[phase]), 3)
            for phase in ("blockout", "refinement")
        },
        "region_phase_priority": {
            key: round(sum(values) / len(values), 3)
            for key, values in sorted(priority.items())
            if values
        },
    }


def _decision_summary(payload: dict[str, Any]) -> dict[str, Any]:
    selected = _selected_segments(payload)
    segments = []
    for node_id, segment in sorted(selected.items()):
        segments.append(
            {
                "node_id": node_id,
                "output_duration_seconds": float(
                    segment.get("output_duration_seconds", 0.0)
                ),
                "hair_region": str(segment.get("hair_region", "not_hair")),
                "process_phase": str(segment.get("process_phase", "other")),
                "importance": float(segment.get("importance", 0.0)),
            }
        )
    return {
        "selected_count": len(segments),
        "selected_duration_seconds": round(
            sum(item["output_duration_seconds"] for item in segments),
            3,
        ),
        "segments": segments,
    }
