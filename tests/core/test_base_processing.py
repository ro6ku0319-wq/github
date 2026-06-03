import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.core.base_processing import BaseProcessor, OutputVideoSettings


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> None:
        self.commands.append(command)


def create_processor(runner: RecordingRunner) -> BaseProcessor:
    return BaseProcessor(
        runner,
        OutputVideoSettings(1080, 1920, 30, "yuv420p"),
    )


def escaped_concat_path(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "'\\''")


def test_output_video_settings_are_immutable() -> None:
    settings = OutputVideoSettings(1080, 1920, 30, "yuv420p")

    with pytest.raises(FrozenInstanceError):
        settings.fps = 60


def test_create_full_concat_writes_manifest_creates_parents_and_normalizes_output(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    processor = create_processor(runner)
    videos = [tmp_path / "input" / "part1.mp4", tmp_path / "input" / "part2.mov"]
    output = tmp_path / "nested" / "video" / "full_concat.mp4"
    concat_list = tmp_path / "nested" / "manifest" / "concat.txt"

    processor.create_full_concat(videos, output, concat_list)

    assert output.parent.is_dir()
    assert concat_list.parent.is_dir()
    assert concat_list.read_text(encoding="utf-8") == "".join(
        f"file '{escaped_concat_path(video)}'\n" for video in videos
    )
    assert runner.commands == [
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output),
        ]
    ]


def test_create_full_concat_safely_escapes_apostrophes_in_manifest(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    processor = create_processor(runner)
    video = tmp_path / "input" / "artist's clip.mp4"
    concat_list = tmp_path / "concat.txt"

    processor.create_full_concat([video], tmp_path / "full_concat.mp4", concat_list)

    assert concat_list.read_text(encoding="utf-8") == (
        f"file '{escaped_concat_path(video)}'\n"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics only")
def test_create_full_concat_manifest_uses_forward_slashes_for_windows_paths(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    processor = create_processor(runner)
    video = tmp_path / "input videos" / "part1.mp4"
    concat_list = tmp_path / "concat.txt"

    processor.create_full_concat([video], tmp_path / "full_concat.mp4", concat_list)

    manifest = concat_list.read_text(encoding="utf-8")
    assert manifest == f"file '{video.resolve().as_posix()}'\n"
    assert "\\" not in manifest


def test_create_full_concat_rejects_empty_video_list_clearly(tmp_path: Path) -> None:
    runner = RecordingRunner()
    processor = create_processor(runner)

    with pytest.raises(ValueError, match=r"至少需要一个输入视频"):
        processor.create_full_concat(
            [],
            tmp_path / "full_concat.mp4",
            tmp_path / "concat.txt",
        )

    assert runner.commands == []


def test_create_accelerated_base_creates_parent_and_uses_settings(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner()
    processor = create_processor(runner)
    source = tmp_path / "full_concat.mp4"
    output = tmp_path / "nested" / "video" / "accelerated_base.mp4"

    processor.create_accelerated_base(source, output, factor=8.0)

    assert output.parent.is_dir()
    assert runner.commands == [
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vf",
            "setpts=PTS/8.0",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(output),
        ]
    ]


@pytest.mark.parametrize("factor", [0.0, -0.5, float("nan"), float("inf")])
def test_create_accelerated_base_rejects_invalid_factor_clearly(
    tmp_path: Path,
    factor: float,
) -> None:
    runner = RecordingRunner()
    processor = create_processor(runner)

    with pytest.raises(ValueError, match=r"加速倍数必须大于 0"):
        processor.create_accelerated_base(
            tmp_path / "full_concat.mp4",
            tmp_path / "accelerated_base.mp4",
            factor,
        )

    assert runner.commands == []
