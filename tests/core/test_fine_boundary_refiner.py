from __future__ import annotations

from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from src.core.coarse_segmenter import NodeCandidate
from src.core.fine_boundary_refiner import FineBoundaryRefiner


class FakeCapture:
    def __init__(self, frames: list) -> None:
        self.frames = frames
        self.position = 0

    def isOpened(self) -> bool:
        return True

    def get(self, property_id: int) -> float:
        if property_id == cv2.CAP_PROP_FPS:
            return 10.0
        if property_id == cv2.CAP_PROP_FRAME_COUNT:
            return float(len(self.frames))
        return 0.0

    def set(self, property_id: int, value: float) -> bool:
        if property_id == cv2.CAP_PROP_POS_FRAMES:
            self.position = int(value)
        return True

    def read(self):
        if self.position >= len(self.frames):
            return False, None
        frame = self.frames[self.position]
        self.position += 1
        return True, frame

    def release(self) -> None:
        pass


def candidate(tmp_path: Path) -> NodeCandidate:
    return NodeCandidate(
        node_id="node_0001",
        label="hair_detail",
        start_global_time=0.0,
        end_global_time=1.0,
        duration_seconds=1.0,
        confidence=0.8,
        score=0.5,
        representative_sample_id="sample_1",
        representative_image_path=tmp_path / "sample.jpg",
        reason="change",
        action_start_frame=0,
        action_peak_frame=5,
        action_completion_frame=10,
        cut_after_frame=12,
        undo_redo_confidence=0.0,
        reverted_to_previous_state=False,
        keep_successful_redo_only=False,
    )


def test_fine_boundary_refiner_finds_action_frames_and_hold_cut(tmp_path: Path) -> None:
    dark = np.zeros((40, 40, 3), dtype=np.uint8)
    bright = np.full((40, 40, 3), 255, dtype=np.uint8)
    frames = [dark.copy() for _ in range(20)]
    frames[5:12] = [bright.copy() for _ in range(7)]
    refiner = FineBoundaryRefiner(capture_factory=lambda _path: FakeCapture(frames))

    result = refiner.refine(
        tmp_path / "source.mp4",
        [candidate(tmp_path)],
        every_n_frames=1,
        search_window_seconds=1.0,
        completion_hold_frames=3,
    )

    refined = result[0]
    assert refined.action_start_frame == 5
    assert refined.action_peak_frame in {5, 12}
    assert refined.action_completion_frame == 12
    assert refined.cut_after_frame == 15
    assert refined.start_global_time == 0.5
    assert refined.end_global_time == 1.5


def test_fine_boundary_refiner_keeps_coarse_candidate_if_video_cannot_open(
    tmp_path: Path,
) -> None:
    class ClosedCapture(FakeCapture):
        def isOpened(self) -> bool:
            return False

    original = candidate(tmp_path)
    result = FineBoundaryRefiner(
        capture_factory=lambda _path: ClosedCapture([]),
    ).refine(
        tmp_path / "missing.mp4",
        [original],
        every_n_frames=2,
        search_window_seconds=1.0,
        completion_hold_frames=3,
    )

    assert result == [original]
