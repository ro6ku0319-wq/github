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
    image_path: Path
    brightness: float
    edge_density: float
    diff_score: float
    edge_diff_score: float
    region_change_score: float
    activity_score: float
    black_frame: bool


def extract_visual_features(samples: list[FrameSample]) -> list[FrameFeature]:
    features: list[FrameFeature] = []
    previous_gray = None
    previous_edges = None

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
        else:
            gray_for_diff, previous_for_diff = _same_size(gray, previous_gray)
            edges_for_diff, previous_edges_for_diff = _same_size(edges, previous_edges)
            diff = cv2.absdiff(gray_for_diff, previous_for_diff)
            edge_diff = cv2.absdiff(edges_for_diff, previous_edges_for_diff)
            diff_score = float(np.mean(diff) / 255.0)
            edge_diff_score = float(np.mean(edge_diff) / 255.0)
            region_change_score = _region_change_score(diff)

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
                image_path=sample.image_path,
                brightness=round(brightness, 6),
                edge_density=round(edge_density, 6),
                diff_score=round(diff_score, 6),
                edge_diff_score=round(edge_diff_score, 6),
                region_change_score=round(region_change_score, 6),
                activity_score=round(activity_score, 6),
                black_frame=black_frame,
            )
        )
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
