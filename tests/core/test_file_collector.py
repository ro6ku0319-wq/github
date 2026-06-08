import os
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from src.core.file_collector import (
    CollectionResult,
    InputDirectoryEmptyError,
    InputVideo,
    collect_videos,
    write_order_file,
)


def create_video(path: Path, modified_time: float = 100.0) -> None:
    path.write_text("", encoding="utf-8")
    os.utime(path, (modified_time, modified_time))


def filenames(videos: tuple[InputVideo, ...]) -> tuple[str, ...]:
    return tuple(video.path.name for video in videos)


def test_order_file_wins_and_warns_about_omitted_supported_inputs(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "part1.mp4")
    create_video(input_dir / "part2.mp4")
    create_video(input_dir / "part3.mp4")
    order_file = tmp_path / "order.txt"
    order_file.write_text("part3.mp4\n\npart1.mp4\n", encoding="utf-8")

    result = collect_videos(input_dir, order_file)

    assert filenames(result.files) == ("part3.mp4", "part1.mp4")
    assert "order_file_omits_input: part2.mp4" in result.warnings


def test_natural_sorting_orders_numeric_filename_parts_numerically(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "part10.mp4")
    create_video(input_dir / "part2.mp4")

    result = collect_videos(input_dir, tmp_path / "missing-order.txt")

    assert filenames(result.files) == ("part2.mp4", "part10.mp4")
    assert filenames(result.natural_order) == ("part2.mp4", "part10.mp4")


def test_empty_input_directory_raises_clear_error(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()

    with pytest.raises(
        InputDirectoryEmptyError,
        match=r"no supported video files",
    ):
        collect_videos(input_dir, tmp_path / "missing-order.txt")


def test_order_file_missing_reference_raises_clear_error(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "part1.mp4")
    order_file = tmp_path / "order.txt"
    order_file.write_text("missing.mp4\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"missing\.mp4"):
        collect_videos(input_dir, order_file)


def test_order_file_rejects_case_insensitive_duplicate_entries(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "Clip.MP4")
    order_file = tmp_path / "order.txt"
    order_file.write_text("Clip.MP4\nclip.mp4\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"duplicate.*clip\.mp4"):
        collect_videos(input_dir, order_file)


def test_existing_blank_order_file_raises_clear_error(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "part1.mp4")
    order_file = tmp_path / "order.txt"
    order_file.write_text(" \n\t\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"blank"):
        collect_videos(input_dir, order_file)


def test_order_file_lookup_is_case_insensitive_and_preserves_actual_filename(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "Clip.MP4")
    order_file = tmp_path / "order.txt"
    order_file.write_text("clip.mp4\n", encoding="utf-8")

    result = collect_videos(input_dir, order_file)

    assert filenames(result.files) == ("Clip.MP4",)


def test_order_file_accepts_utf8_bom(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "part1.mp4")
    order_file = tmp_path / "order.txt"
    order_file.write_text("part1.mp4\n", encoding="utf-8-sig")

    result = collect_videos(input_dir, order_file)

    assert filenames(result.files) == ("part1.mp4",)


def test_filters_extensions_case_insensitively_and_ignores_nested_files(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    nested_dir = input_dir / "nested"
    nested_dir.mkdir()
    create_video(input_dir / "clip.MP4")
    create_video(input_dir / "scene.MoV")
    create_video(input_dir / "take.mkv")
    create_video(input_dir / "ignored.avi")
    create_video(nested_dir / "nested.mp4")

    result = collect_videos(input_dir, tmp_path / "missing-order.txt")

    assert filenames(result.files) == ("clip.MP4", "scene.MoV", "take.mkv")


def test_warns_when_natural_and_modified_time_orders_conflict(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "part1.mp4", modified_time=200.0)
    create_video(input_dir / "part2.mp4", modified_time=100.0)

    result = collect_videos(input_dir, tmp_path / "missing-order.txt")

    assert filenames(result.natural_order) == ("part1.mp4", "part2.mp4")
    assert filenames(result.modified_time_order) == ("part2.mp4", "part1.mp4")
    assert "filename_and_mtime_order_conflict" in result.warnings


def test_nonnumeric_filenames_use_modified_time_order_with_warning(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "alpha.mp4", modified_time=200.0)
    create_video(input_dir / "beta.mp4", modified_time=100.0)

    result = collect_videos(input_dir, tmp_path / "missing-order.txt")

    assert filenames(result.natural_order) == ("alpha.mp4", "beta.mp4")
    assert filenames(result.modified_time_order) == ("beta.mp4", "alpha.mp4")
    assert filenames(result.files) == ("beta.mp4", "alpha.mp4")
    assert "filename_order_unreliable_using_mtime" in result.warnings
    assert "filename_and_mtime_order_conflict" in result.warnings


def test_discovered_video_paths_are_resolved(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    video_path = input_dir / "part1.mp4"
    create_video(video_path)

    result = collect_videos(input_dir, tmp_path / "missing-order.txt")

    assert result.files[0].path == video_path.resolve()


def test_rejects_case_insensitive_ambiguous_discovered_filenames_when_supported(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    create_video(input_dir / "Clip.MP4")
    create_video(input_dir / "clip.mp4")
    discovered_filenames = tuple(path.name for path in input_dir.iterdir())
    if len(discovered_filenames) < 2:
        pytest.skip("filesystem does not support case-ambiguous filenames")

    with pytest.raises(ValueError, match=r"ambiguous"):
        collect_videos(input_dir, tmp_path / "missing-order.txt")


def test_write_order_file_creates_parent_and_writes_exact_content(
    tmp_path: Path,
) -> None:
    order_file = tmp_path / "nested" / "order.txt"

    write_order_file(order_file, ["part2.mp4", "part10.mp4"])

    assert order_file.read_text(encoding="utf-8") == "part2.mp4\npart10.mp4\n"


def test_input_video_and_collection_result_are_immutable(tmp_path: Path) -> None:
    video = InputVideo(path=tmp_path / "part1.mp4", modified_time=100.0)
    result = CollectionResult(
        files=(video,),
        natural_order=(video,),
        modified_time_order=(video,),
        warnings=(),
    )

    with pytest.raises(FrozenInstanceError):
        video.modified_time = 200.0

    with pytest.raises(FrozenInstanceError):
        result.files = ()
