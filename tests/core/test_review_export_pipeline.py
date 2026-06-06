from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.core.review_export_pipeline import ReviewExportPipeline


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> None:
        self.commands.append(command)


def write_cut_decision(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "node_id,label,start_global_time,end_global_time,duration_seconds,confidence,"
        "keep_in_body_45s,keep_in_body_60s,keep_in_body_120s,speed_multiplier,"
        "reason,human_note\n"
        "node_0001,hair_detail,0.000,4.000,4.000,0.900,true,true,true,1.000,"
        "high change,front hair\n"
        "node_0002,zoom_pan_view,4.000,8.000,4.000,0.600,false,true,true,1.000,"
        "transition,short pan\n"
        "node_0003,static_low_value,8.000,12.000,4.000,0.300,false,false,true,1.000,"
        "low value,optional\n",
        encoding="utf-8",
    )


def test_review_export_pipeline_creates_body_cuts_preview_and_markers(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    source = output_dir / "accelerated_base.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"placeholder")
    write_cut_decision(output_dir / "cut_decision.csv")
    runner = FakeRunner()
    logs: list[str] = []
    progress: list[tuple[int, str]] = []

    pipeline = ReviewExportPipeline(
        tmp_path,
        {
            "output": {"output_dir": "output"},
            "cut_versions": {
                "body_45s": {"enabled": True, "target_duration_seconds": 5},
                "body_60s": {"enabled": True, "target_duration_seconds": 6},
                "body_120s": {"enabled": True, "target_duration_seconds": 20},
            },
            "output_video": {"pixel_format": "yuv420p"},
        },
        log=logs.append,
        progress=lambda value, message: progress.append((value, message)),
        runner=runner,
    )

    result = pipeline.run_all()

    assert [path.name for path in result.body_cut_outputs] == [
        "body_cut_45s.mp4",
        "body_cut_60s.mp4",
        "body_cut_120s.mp4",
    ]
    assert result.preview_output == output_dir / "auto_node_preview.mp4"
    assert result.marker_output == output_dir / "davinci_markers.csv"
    assert len(runner.commands) == 4
    command_text = "\n".join(" ".join(command) for command in runner.commands)
    assert "body_cut_45s.mp4" in command_text
    assert "body_cut_60s.mp4" in command_text
    assert "body_cut_120s.mp4" in command_text
    assert "auto_node_preview.mp4" in command_text
    assert "trim=start=0.000:end=4.000" in command_text
    assert "concat=n=" in command_text

    marker_rows = list(
        csv.DictReader((output_dir / "davinci_markers.csv").open(encoding="utf-8"))
    )
    assert [row["node_id"] for row in marker_rows] == [
        "node_0001",
        "node_0002",
        "node_0003",
    ]
    assert progress[-1][0] == 100
    assert any("导出完成" in message for message in logs)


def test_review_export_requires_cut_decision_csv(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "accelerated_base.mp4").write_bytes(b"placeholder")
    pipeline = ReviewExportPipeline(tmp_path, {}, runner=FakeRunner())

    with pytest.raises(FileNotFoundError, match="cut_decision.csv"):
        pipeline.run_all()
