from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.core.image_io import write_image
from src.core.visual_feature_extractor import FrameFeature


def write_activity_curve_png(path: Path, features: list[FrameFeature]) -> None:
    canvas = np.full((320, 1000, 3), 255, dtype=np.uint8)
    cv2.line(canvas, (60, 260), (960, 260), (200, 200, 200), 1)
    cv2.line(canvas, (60, 40), (60, 260), (200, 200, 200), 1)
    cv2.putText(
        canvas,
        "activity curve",
        (60, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (40, 40, 40),
        2,
        cv2.LINE_AA,
    )
    if len(features) >= 2:
        max_time = max(item.time_seconds for item in features) or 1.0
        points = []
        for feature in features:
            x = 60 + int((feature.time_seconds / max_time) * 900)
            y = 260 - int(min(1.0, feature.activity_score) * 210)
            points.append((x, y))
        for start, end in zip(points, points[1:]):
            cv2.line(canvas, start, end, (40, 110, 220), 2, cv2.LINE_AA)
        for feature, point in zip(features, points):
            color = (40, 40, 40) if not feature.black_frame else (20, 20, 20)
            cv2.circle(canvas, point, 3, color, -1)
    write_image(path, canvas, ".png")
