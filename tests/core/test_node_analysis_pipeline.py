from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from src.core.frame_sampler import FrameSample
from src.core.node_analysis_pipeline import NodeAnalysisPipeline


def write_frame(path: Path, value: int, offset: int = 0) -> None:
    image = np.full((90, 50, 3), value, dtype=np.uint8)
    if offset:
        cv2.rectangle(image, (5 + offset, 15), (35 + offset, 70), (255, 255, 255), -1)
        cv2.line(image, (0, 0), (49, 89), (0, 0, 0), 2)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), image)


class FakeSampler:
    def __init__(self, samples: list[FrameSample]) -> None:
        self.samples = samples
        self.calls: list[tuple[Path, Path, float]] = []

    def sample(self, source: Path, frames_dir: Path, interval_seconds: float) -> list[FrameSample]:
        self.calls.append((source, frames_dir, interval_seconds))
        return self.samples


def test_node_analysis_writes_review_outputs_from_accelerated_base(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "output"
    source = output_dir / "accelerated_base.mp4"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"placeholder")

    frame_dir = tmp_path / "sample_frames"
    paths = [frame_dir / f"sample_{index:03d}.jpg" for index in range(6)]
    write_frame(paths[0], 80)
    write_frame(paths[1], 90, 1)
    write_frame(paths[2], 90, 8)
    write_frame(paths[3], 90, 8)
    write_frame(paths[4], 0)
    write_frame(paths[5], 80)
    samples = [
        FrameSample(
            sample_id=f"sample_{index:06d}",
            time_seconds=index * 0.5,
            frame_index=index * 15,
            image_path=path,
            width=50,
            height=90,
        )
        for index, path in enumerate(paths)
    ]
    sampler = FakeSampler(samples)
    logs: list[str] = []
    progress: list[tuple[int, str]] = []

    pipeline = NodeAnalysisPipeline(
        tmp_path,
        {
            "output": {"output_dir": "output"},
            "fine_cut": {
                "coarse_sample_interval_seconds": 0.5,
                "min_node_duration_seconds": 0.25,
            },
        },
        log=logs.append,
        progress=lambda value, message: progress.append((value, message)),
        sampler=sampler,
    )

    result = pipeline.run_all()

    assert sampler.calls == [(source.resolve(), output_dir / "frame_cache", 0.5)]
    assert result.candidates
    assert result.candidates[0].start_global_time >= 0
    assert result.candidates[0].end_global_time > result.candidates[0].start_global_time

    manifest = json.loads((output_dir / "frame_manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"].endswith("accelerated_base.mp4")
    assert len(manifest["samples"]) == len(samples)

    score_rows = list(
        csv.DictReader((output_dir / "operation_score_table.csv").open(encoding="utf-8"))
    )
    assert len(score_rows) == len(samples)
    assert {"sample_id", "activity_score", "black_frame"} <= set(score_rows[0])

    decision_rows = list(
        csv.DictReader((output_dir / "cut_decision.csv").open(encoding="utf-8"))
    )
    assert decision_rows
    for expected in (
        "node_id",
        "label",
        "start_global_time",
        "end_global_time",
        "duration_seconds",
        "confidence",
        "keep_in_body_45s",
        "keep_in_body_60s",
        "keep_in_body_120s",
        "speed_multiplier",
        "reason",
        "human_note",
    ):
        assert expected in decision_rows[0]
    assert decision_rows[0]["keep_in_body_60s"] in {"true", "false"}
    assert decision_rows[0]["reason"]

    assert (output_dir / "node_analysis.json").exists()
    assert (output_dir / "node_contact_sheet.jpg").read_bytes().startswith(b"\xff\xd8")
    assert (output_dir / "activity_curve.png").read_bytes().startswith(b"\x89PNG")
    assert progress[-1][0] == 100
    assert any("节点分析完成" in message for message in logs)


def test_node_analysis_requires_accelerated_base(tmp_path: Path) -> None:
    pipeline = NodeAnalysisPipeline(tmp_path, {}, sampler=FakeSampler([]))

    with pytest.raises(FileNotFoundError, match="accelerated_base.mp4"):
        pipeline.run_all()
