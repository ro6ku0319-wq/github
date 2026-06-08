from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.core.timeline_mapper import TimelineRange, build_timeline
from src.core.video_probe import VideoMetadata


def metadata(path: str, duration_seconds: float) -> VideoMetadata:
    return VideoMetadata(
        path=Path(path),
        duration_seconds=duration_seconds,
        width=1920,
        height=1080,
        fps=30.0,
        codec="h264",
        has_audio=False,
        modified_time=1.0,
    )


def test_build_timeline_maps_global_and_source_ranges() -> None:
    videos = [metadata("part1.mp4", 42.0), metadata("part2.mp4", 36.0)]

    ranges = build_timeline(videos)

    assert ranges == [
        TimelineRange(
            source_file="part1.mp4",
            global_start=0.0,
            global_end=42.0,
            source_start=0.0,
            source_end=42.0,
        ),
        TimelineRange(
            source_file="part2.mp4",
            global_start=42.0,
            global_end=78.0,
            source_start=0.0,
            source_end=36.0,
        ),
    ]


def test_build_timeline_returns_empty_list_for_no_videos() -> None:
    assert build_timeline([]) == []


@pytest.mark.parametrize("duration_seconds", [0.0, -1.0])
def test_build_timeline_rejects_nonpositive_duration(
    duration_seconds: float,
) -> None:
    with pytest.raises(ValueError, match=r"part1\.mp4.*positive duration"):
        build_timeline([metadata("part1.mp4", duration_seconds)])


def test_timeline_range_is_immutable() -> None:
    timeline_range = TimelineRange("part1.mp4", 0.0, 42.0, 0.0, 42.0)

    with pytest.raises(FrozenInstanceError):
        timeline_range.global_end = 10.0
