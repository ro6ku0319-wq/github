from __future__ import annotations

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from src.core.coarse_segmenter import build_candidate_nodes
from src.core.frame_sampler import FrameSample
from src.core.visual_feature_extractor import extract_visual_features


def _write(path: Path, image) -> FrameSample:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(path), image)
    return FrameSample(path.stem, 0.0, 0, path, image.shape[1], image.shape[0])


def test_visual_features_include_global_center_ui_density_and_repetition(
    tmp_path: Path,
) -> None:
    state_a = np.zeros((100, 100, 3), dtype=np.uint8)
    state_b = state_a.copy()
    cv2.rectangle(state_b, (35, 35), (65, 65), (255, 255, 255), -1)
    samples = [
        _write(tmp_path / "a1.jpg", state_a),
        _write(tmp_path / "b.jpg", state_b),
        _write(tmp_path / "a2.jpg", state_a),
    ]
    samples = [
        FrameSample(item.sample_id, index * 0.5, index * 15, item.image_path, 100, 100)
        for index, item in enumerate(samples)
    ]

    features = extract_visual_features(samples)

    changed = features[1]
    reverted = features[2]
    assert changed.global_diff_score == changed.diff_score
    assert changed.center_diff_score > changed.ui_diff_score
    assert changed.local_change_density > 0
    assert changed.brightness_score == changed.brightness
    assert changed.detail_score == changed.edge_density
    assert reverted.reverted_to_previous_state is True
    assert reverted.repetition_score > 0.9


def test_candidate_nodes_expose_boundary_frames_and_undo_redo_fields(
    tmp_path: Path,
) -> None:
    state_a = np.zeros((100, 100, 3), dtype=np.uint8)
    state_b = state_a.copy()
    cv2.rectangle(state_b, (20, 20), (80, 80), (255, 255, 255), -1)
    images = [state_a, state_b, state_a]
    samples = []
    for index, image in enumerate(images):
        path = tmp_path / f"sample_{index}.jpg"
        cv2.imwrite(str(path), image)
        samples.append(FrameSample(f"s{index}", index * 0.5, index * 15, path, 100, 100))

    candidates = build_candidate_nodes(
        extract_visual_features(samples),
        min_node_duration_seconds=0.25,
        sample_interval_seconds=0.5,
        completion_hold_frames=3,
    )

    assert candidates
    candidate = candidates[-1]
    assert candidate.action_start_frame >= 0
    assert candidate.action_peak_frame >= candidate.action_start_frame
    assert candidate.action_completion_frame >= candidate.action_peak_frame
    assert candidate.cut_after_frame == candidate.action_completion_frame + 3
    assert isinstance(candidate.reverted_to_previous_state, bool)
    assert 0 <= candidate.undo_redo_confidence <= 1
    assert isinstance(candidate.keep_successful_redo_only, bool)
