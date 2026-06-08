from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2

from src.core.image_io import write_image


@dataclass(frozen=True)
class FrameSample:
    sample_id: str
    time_seconds: float
    frame_index: int
    image_path: Path
    width: int
    height: int


class FrameSampler:
    def __init__(self, thumbnail_width: int = 320) -> None:
        if thumbnail_width <= 0:
            raise ValueError("thumbnail_width must be positive")
        self.thumbnail_width = thumbnail_width

    def sample(
        self,
        source: Path,
        frames_dir: Path,
        interval_seconds: float,
    ) -> list[FrameSample]:
        if interval_seconds <= 0:
            raise ValueError("coarse sample interval must be positive")

        source = Path(source).resolve()
        frames_dir = Path(frames_dir)
        frames_dir.mkdir(parents=True, exist_ok=True)

        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise RuntimeError(f"无法打开视频进行抽帧: {source}")

        try:
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 30.0)
            if fps <= 0:
                fps = 30.0
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration = frame_count / fps if frame_count > 0 else 0.0
            sample_times = self._sample_times(duration, interval_seconds)
            samples: list[FrameSample] = []
            for index, time_seconds in enumerate(sample_times):
                capture.set(cv2.CAP_PROP_POS_MSEC, time_seconds * 1000.0)
                ok, frame = capture.read()
                if not ok:
                    continue
                thumbnail = self._resize(frame)
                sample_id = f"sample_{index:06d}"
                image_path = frames_dir / f"{sample_id}_{int(time_seconds * 1000):09d}ms.jpg"
                write_image(image_path, thumbnail, ".jpg")
                height, width = thumbnail.shape[:2]
                samples.append(
                    FrameSample(
                        sample_id=sample_id,
                        time_seconds=round(time_seconds, 3),
                        frame_index=int(round(time_seconds * fps)),
                        image_path=image_path,
                        width=width,
                        height=height,
                    )
                )
        finally:
            capture.release()

        if not samples:
            raise RuntimeError(f"未能从视频中抽取任何帧: {source}")
        return samples

    @staticmethod
    def _sample_times(duration: float, interval_seconds: float) -> list[float]:
        if duration <= 0:
            return [0.0]
        count = int(duration // interval_seconds) + 1
        times = [index * interval_seconds for index in range(count)]
        if times[-1] < duration:
            times.append(duration)
        return times

    def _resize(self, frame):
        height, width = frame.shape[:2]
        if width <= self.thumbnail_width:
            return frame
        target_height = max(1, int(round(height * (self.thumbnail_width / width))))
        return cv2.resize(frame, (self.thumbnail_width, target_height), interpolation=cv2.INTER_AREA)
