from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from src.core.llm_package_builder import LlmPackageBuilder


def write_frame(path: Path, value: int) -> None:
    image = np.full((120, 80, 3), value, dtype=np.uint8)
    cv2.line(image, (0, 0), (79, 119), (255 - value, 255 - value, 255 - value), 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), image)


def test_llm_package_builder_creates_manual_review_package(tmp_path: Path) -> None:
    output = tmp_path / "output"
    frame_cache = output / "frame_cache"
    frame_paths = [frame_cache / f"sample_{index:06d}.jpg" for index in range(4)]
    for index, path in enumerate(frame_paths):
        write_frame(path, 40 + index * 40)

    (output / "frame_manifest.json").write_text(
        json.dumps(
            {
                "source": str(output / "accelerated_base.mp4"),
                "samples": [
                    {
                        "sample_id": f"sample_{index:06d}",
                        "time_seconds": index * 2.0,
                        "frame_index": index * 60,
                        "image_path": str(path),
                        "width": 80,
                        "height": 120,
                    }
                    for index, path in enumerate(frame_paths)
                ],
            }
        ),
        encoding="utf-8",
    )
    (output / "operation_score_table.csv").write_text(
        "sample_id,time_seconds,activity_score,black_frame\n"
        "sample_000000,0.000,0.100,false\n"
        "sample_000001,2.000,0.900,false\n"
        "sample_000002,4.000,0.600,false\n"
        "sample_000003,6.000,0.200,false\n",
        encoding="utf-8",
    )
    (output / "cut_decision.csv").write_text(
        "node_id,label,start_global_time,end_global_time,reason\n"
        "node_0001,hair_detail,1.000,3.000,high change\n",
        encoding="utf-8",
    )
    (output / "node_contact_sheet.jpg").write_bytes(frame_paths[0].read_bytes())
    logs: list[str] = []

    result = LlmPackageBuilder(
        tmp_path,
        {
            "output": {"output_dir": "output"},
            "llm_package": {
                "overview_sample_interval_seconds": 2,
                "max_contact_sheet_items_per_page": 60,
            },
        },
        log=logs.append,
    ).build()

    package = output / "llm_review_package"
    assert result.package_dir == package
    for relative in (
        "overview_contact_sheet.jpg",
        "node_contact_sheet_01.jpg",
        "high_detail_contact_sheet.jpg",
        "frame_manifest.json",
        "operation_candidates.csv",
        "llm_prompt.md",
    ):
        assert (package / relative).exists()
    assert len(list((package / "frames").glob("F*.jpg"))) == 4
    manifest = json.loads((package / "frame_manifest.json").read_text(encoding="utf-8"))
    assert manifest["frames"][0]["frame_id"] == "F001"
    assert manifest["frames"][0]["global_timecode"] == "00:00:00.0"
    assert manifest["frames"][0]["image_file"] == "frames/F001.jpg"
    prompt = (package / "llm_prompt.md").read_text(encoding="utf-8")
    assert '"video_type": "body_cut_only"' in prompt
    assert "不要编造真实笔刷名称" in prompt
    assert "keep_speedup_inside_candidate_range" in prompt
    assert "edit_action 只能使用" in prompt
    assert "keep_as_body_cut_end_state" in prompt
    candidates = list(
        csv.DictReader((package / "operation_candidates.csv").open(encoding="utf-8"))
    )
    assert candidates[0]["node_id"] == "node_0001"
    assert any("LLM 视觉证据包完成" in message for message in logs)


def test_llm_package_builder_requires_node_analysis_outputs(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="frame_manifest.json"):
        LlmPackageBuilder(tmp_path, {}).build()
