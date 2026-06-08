from __future__ import annotations

import math
from dataclasses import dataclass

from src.core.video_probe import VideoMetadata


@dataclass(frozen=True)
class TimelineRange:
    source_file: str
    global_start: float
    global_end: float
    source_start: float
    source_end: float


def _positive_duration(video: VideoMetadata) -> float:
    duration = video.duration_seconds
    if (
        isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or not math.isfinite(duration)
        or duration <= 0
    ):
        raise ValueError(
            f"Video {video.path} must have a finite positive duration; got {duration!r}"
        )
    return float(duration)


def build_timeline(videos: list[VideoMetadata]) -> list[TimelineRange]:
    cursor = 0.0
    result: list[TimelineRange] = []
    for video in videos:
        duration = _positive_duration(video)
        global_end = cursor + duration
        if not math.isfinite(global_end):
            raise ValueError(f"Timeline duration is not finite after video {video.path}")
        result.append(
            TimelineRange(
                source_file=str(video.path),
                global_start=cursor,
                global_end=global_end,
                source_start=0.0,
                source_end=duration,
            )
        )
        cursor = global_end
    return result
