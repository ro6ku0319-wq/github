from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from src.core.coarse_segmenter import NodeCandidate


class FineBoundaryRefiner:
    def __init__(
        self,
        capture_factory: Callable[[str], Any] | None = None,
        analysis_width: int = 240,
    ) -> None:
        self.capture_factory = capture_factory or cv2.VideoCapture
        self.analysis_width = max(32, analysis_width)

    def refine(
        self,
        source: Path,
        candidates: list[NodeCandidate],
        every_n_frames: int,
        search_window_seconds: float,
        completion_hold_frames: int,
    ) -> list[NodeCandidate]:
        if not candidates:
            return []
        capture = self.capture_factory(str(Path(source).resolve()))
        if not capture.isOpened():
            capture.release()
            return candidates
        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
            if fps <= 0:
                fps = 30.0
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            return [
                self._refine_candidate(
                    capture,
                    candidate,
                    fps=fps,
                    frame_count=frame_count,
                    every_n_frames=max(1, every_n_frames),
                    search_window_seconds=max(0.0, search_window_seconds),
                    completion_hold_frames=max(0, completion_hold_frames),
                )
                for candidate in candidates
            ]
        finally:
            capture.release()

    def _refine_candidate(
        self,
        capture: Any,
        candidate: NodeCandidate,
        fps: float,
        frame_count: int,
        every_n_frames: int,
        search_window_seconds: float,
        completion_hold_frames: int,
    ) -> NodeCandidate:
        margin = int(round(search_window_seconds * fps))
        start_frame = max(0, candidate.action_start_frame - margin)
        end_frame = candidate.cut_after_frame + margin
        if frame_count > 0:
            end_frame = min(frame_count - 1, end_frame)
        observations = self._read_differences(
            capture,
            start_frame,
            end_frame,
            every_n_frames,
        )
        if len(observations) < 2:
            return candidate

        peak_frame, peak_score = max(observations, key=lambda item: item[1])
        if peak_score <= 0:
            return candidate
        threshold = max(0.01, peak_score * 0.25)
        active_frames = [
            frame_index
            for frame_index, score in observations
            if score >= threshold
        ]
        if not active_frames:
            return candidate
        action_start = active_frames[0]
        action_completion = active_frames[-1]
        cut_after = action_completion + completion_hold_frames
        if frame_count > 0:
            cut_after = min(frame_count - 1, cut_after)
        if cut_after <= action_start:
            return candidate
        start_seconds = action_start / fps
        end_seconds = cut_after / fps
        return replace(
            candidate,
            start_global_time=round(start_seconds, 3),
            end_global_time=round(end_seconds, 3),
            duration_seconds=round(end_seconds - start_seconds, 3),
            action_start_frame=action_start,
            action_peak_frame=peak_frame,
            action_completion_frame=action_completion,
            cut_after_frame=cut_after,
        )

    def _read_differences(
        self,
        capture: Any,
        start_frame: int,
        end_frame: int,
        every_n_frames: int,
    ) -> list[tuple[int, float]]:
        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        observations: list[tuple[int, float]] = []
        previous_gray: np.ndarray | None = None
        current_frame = start_frame
        while current_frame <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break
            if (current_frame - start_frame) % every_n_frames == 0:
                gray = self._gray(frame)
                score = 0.0
                if previous_gray is not None:
                    score = float(np.mean(cv2.absdiff(gray, previous_gray)) / 255.0)
                observations.append((current_frame, score))
                previous_gray = gray
            current_frame += 1
        return observations

    def _gray(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        height, width = gray.shape[:2]
        if width <= self.analysis_width:
            return gray
        target_height = max(1, int(round(height * (self.analysis_width / width))))
        return cv2.resize(
            gray,
            (self.analysis_width, target_height),
            interpolation=cv2.INTER_AREA,
        )
