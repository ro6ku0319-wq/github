import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv"}


class InputDirectoryEmptyError(ValueError):
    pass


@dataclass(frozen=True)
class InputVideo:
    path: Path
    modified_time: float


@dataclass(frozen=True)
class CollectionResult:
    files: tuple[InputVideo, ...]
    natural_order: tuple[InputVideo, ...]
    modified_time_order: tuple[InputVideo, ...]
    warnings: tuple[str, ...]


def _natural_key(video: InputVideo) -> tuple[tuple[int, object], ...]:
    tokens = tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", video.path.name)
    )
    return (*tokens, (2, video.path.name.casefold()), (3, video.path.name))


def collect_videos(input_dir: Path, order_file: Path) -> CollectionResult:
    input_dir = Path(input_dir)
    order_file = Path(order_file)
    videos = tuple(
        InputVideo(path=path.resolve(), modified_time=path.stat().st_mtime)
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS
    )
    if not videos:
        raise InputDirectoryEmptyError(
            f"Input directory has no supported video files: {input_dir}"
        )

    videos_by_name = {}
    for video in videos:
        normalized_name = video.path.name.casefold()
        if normalized_name in videos_by_name:
            raise ValueError(
                "Input directory contains case-insensitive ambiguous video filenames: "
                f"{videos_by_name[normalized_name].path.name}, {video.path.name}"
            )
        videos_by_name[normalized_name] = video

    natural_order = tuple(sorted(videos, key=_natural_key))
    modified_time_order = tuple(
        sorted(videos, key=lambda video: (video.modified_time, _natural_key(video)))
    )
    warnings = []
    if natural_order != modified_time_order:
        warnings.append("filename_and_mtime_order_conflict")

    files = natural_order
    if order_file.exists():
        listed_filenames = tuple(
            line.strip()
            for line in order_file.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        )
        if not listed_filenames:
            raise ValueError(f"Order file is blank: {order_file}")

        normalized_filenames = tuple(
            filename.casefold() for filename in listed_filenames
        )
        seen_filenames = set()
        for filename, normalized_filename in zip(
            listed_filenames, normalized_filenames
        ):
            if normalized_filename in seen_filenames:
                raise ValueError(
                    f"Order file contains duplicate input video entry: {filename}"
                )
            seen_filenames.add(normalized_filename)

        missing_filenames = [
            filename
            for filename, normalized_filename in zip(
                listed_filenames, normalized_filenames
            )
            if normalized_filename not in videos_by_name
        ]
        if missing_filenames:
            raise ValueError(
                f"Order file references missing input video: {missing_filenames[0]}"
            )

        files = tuple(
            videos_by_name[normalized_filename]
            for normalized_filename in normalized_filenames
        )
        listed_filename_set = set(normalized_filenames)
        warnings.extend(
            f"order_file_omits_input: {video.path.name}"
            for video in natural_order
            if video.path.name.casefold() not in listed_filename_set
        )
    elif not all(re.search(r"\d+", video.path.stem) for video in videos):
        files = modified_time_order
        warnings.append("filename_order_unreliable_using_mtime")

    return CollectionResult(
        files=files,
        natural_order=natural_order,
        modified_time_order=modified_time_order,
        warnings=tuple(warnings),
    )


def write_order_file(order_file: Path, filenames: Iterable[str]) -> None:
    order_file = Path(order_file)
    order_file.parent.mkdir(parents=True, exist_ok=True)
    order_file.write_text(
        "".join(f"{filename}\n" for filename in filenames),
        encoding="utf-8",
    )
