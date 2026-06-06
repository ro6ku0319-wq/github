from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from src.core.coarse_segmenter import NodeCandidate
from src.core.image_io import read_image, write_image


def write_node_contact_sheet(
    path: Path,
    candidates: list[NodeCandidate],
    max_items: int = 60,
) -> None:
    path = Path(path)
    visible = candidates[: max(1, max_items)]
    if not visible:
        canvas = np.full((360, 640, 3), 245, dtype=np.uint8)
        cv2.putText(
            canvas,
            "No node candidates",
            (40, 180),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (40, 40, 40),
            2,
            cv2.LINE_AA,
        )
        write_image(path, canvas, ".jpg")
        return

    cell_width = 260
    cell_height = 420
    columns = min(4, len(visible))
    rows = int(np.ceil(len(visible) / columns))
    canvas = np.full((rows * cell_height, columns * cell_width, 3), 250, dtype=np.uint8)

    for index, candidate in enumerate(visible):
        row = index // columns
        column = index % columns
        x = column * cell_width
        y = row * cell_height
        image = read_image(candidate.representative_image_path)
        thumbnail = _fit(image, cell_width - 24, cell_height - 110)
        top = y + 12
        left = x + (cell_width - thumbnail.shape[1]) // 2
        canvas[top : top + thumbnail.shape[0], left : left + thumbnail.shape[1]] = thumbnail
        text_y = y + cell_height - 84
        _put(canvas, candidate.node_id, x + 12, text_y)
        _put(canvas, candidate.label, x + 12, text_y + 24)
        _put(
            canvas,
            f"{candidate.start_global_time:.2f}-{candidate.end_global_time:.2f}s",
            x + 12,
            text_y + 48,
        )
        _put(canvas, f"conf {candidate.confidence:.2f}", x + 12, text_y + 72)

    write_image(path, canvas, ".jpg")


def _fit(image: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height)
    target_width = max(1, int(width * scale))
    target_height = max(1, int(height * scale))
    return cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_AREA)


def _put(image: np.ndarray, text: str, x: int, y: int) -> None:
    cv2.putText(
        image,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (20, 20, 20),
        1,
        cv2.LINE_AA,
    )
