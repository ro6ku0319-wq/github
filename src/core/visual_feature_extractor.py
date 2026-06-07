from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from src.core.frame_sampler import FrameSample
from src.core.image_io import read_image


@dataclass(frozen=True)
class FrameFeature:
    sample_id: str
    time_seconds: float
    frame_index: int
    image_path: Path
    brightness: float
    edge_density: float
    diff_score: float
    edge_diff_score: float
    region_change_score: float
    activity_score: float
    black_frame: bool
    global_diff_score: float
    center_diff_score: float
    ui_diff_score: float
    local_change_density: float
    brightness_score: float
    detail_score: float
    stability_after_change: float
    novelty_score: float
    repetition_score: float
    reverted_to_previous_state: bool


def extract_visual_features(samples: list[FrameSample]) -> list[FrameFeature]:
    features: list[FrameFeature] = []
    previous_gray = None
    previous_edges = None
    previous_previous_gray = None

    for sample in samples:
        image = read_image(sample.image_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        brightness = float(np.mean(gray) / 255.0)
        edge_density = float(np.count_nonzero(edges) / edges.size)
        black_frame = brightness < 0.025 and edge_density < 0.005

        if previous_gray is None or previous_edges is None:
            diff_score = 0.0
            edge_diff_score = 0.0
            region_change_score = 0.0
            center_diff_score = 0.0
            ui_diff_score = 0.0
            local_change_density = 0.0
        else:
            gray_for_diff, previous_for_diff = _same_size(gray, previous_gray)
            edges_for_diff, previous_edges_for_diff = _same_size(edges, previous_edges)
            diff = cv2.absdiff(gray_for_diff, previous_for_diff)
            edge_diff = cv2.absdiff(edges_for_diff, previous_edges_for_diff)
            diff_score = float(np.mean(diff) / 255.0)
            edge_diff_score = float(np.mean(edge_diff) / 255.0)
            region_change_score = _region_change_score(diff)
            center_diff_score, ui_diff_score = _center_and_ui_scores(diff)
            local_change_density = float(np.count_nonzero(diff >= 20) / diff.size)

        repetition_score = 0.0
        if previous_previous_gray is not None:
            gray_for_repeat, previous_previous_for_repeat = _same_size(
                gray,
                previous_previous_gray,
            )
            repeat_diff = cv2.absdiff(gray_for_repeat, previous_previous_for_repeat)
            repetition_score = max(0.0, 1.0 - float(np.mean(repeat_diff) / 255.0))
        reverted = repetition_score >= 0.97 and diff_score >= 0.01
        stability_after_change = max(0.0, 1.0 - min(1.0, diff_score * 4.0))
        novelty_score = min(1.0, (diff_score * 4.0) + (edge_diff_score * 2.0))

        activity_score = 0.0
        if not black_frame:
            activity_score = min(
                1.0,
                (diff_score * 0.60)
                + (edge_diff_score * 0.30)
                + (region_change_score * 0.10),
            )
        features.append(
            FrameFeature(
                sample_id=sample.sample_id,
                time_seconds=sample.time_seconds,
                frame_index=sample.frame_index,
                image_path=sample.image_path,
                brightness=round(brightness, 6),
                edge_density=round(edge_density, 6),
                diff_score=round(diff_score, 6),
                edge_diff_score=round(edge_diff_score, 6),
                region_change_score=round(region_change_score, 6),
                activity_score=round(activity_score, 6),
                black_frame=black_frame,
                global_diff_score=round(diff_score, 6),
                center_diff_score=round(center_diff_score, 6),
                ui_diff_score=round(ui_diff_score, 6),
                local_change_density=round(local_change_density, 6),
                brightness_score=round(brightness, 6),
                detail_score=round(edge_density, 6),
                stability_after_change=round(stability_after_change, 6),
                novelty_score=round(novelty_score, 6),
                repetition_score=round(repetition_score, 6),
                reverted_to_previous_state=reverted,
            )
        )
        previous_previous_gray = previous_gray
        previous_gray = gray
        previous_edges = edges

    return features


def _same_size(current: np.ndarray, previous: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if current.shape == previous.shape:
        return current, previous
    resized_previous = cv2.resize(
        previous,
        (current.shape[1], current.shape[0]),
        interpolation=cv2.INTER_AREA,
    )
    return current, resized_previous


def _region_change_score(diff: np.ndarray) -> float:
    height, width = diff.shape[:2]
    rows = np.array_split(np.arange(height), 3)
    columns = np.array_split(np.arange(width), 3)
    scores: list[float] = []
    for row_indexes in rows:
        for column_indexes in columns:
            region = diff[np.ix_(row_indexes, column_indexes)]
            if region.size:
                scores.append(float(np.mean(region) / 255.0))
    return max(scores, default=0.0)


def _center_and_ui_scores(diff: np.ndarray) -> tuple[float, float]:
    height, width = diff.shape[:2]
    top = height // 4
    bottom = max(top + 1, height - top)
    left = width // 4
    right = max(left + 1, width - left)
    center = diff[top:bottom, left:right]
    ui_mask = np.ones(diff.shape[:2], dtype=bool)
    ui_mask[top:bottom, left:right] = False
    center_score = float(np.mean(center) / 255.0) if center.size else 0.0
    ui_values = diff[ui_mask]
    ui_score = float(np.mean(ui_values) / 255.0) if ui_values.size else 0.0
    return center_score, ui_score
