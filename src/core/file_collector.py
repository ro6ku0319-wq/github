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
        InputVideo(path=path, modified_time=path.stat().st_mtime)
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS
    )
    if not videos:
        raise InputDirectoryEmptyError(
            f"Input directory has no supported video files: {input_dir}"
        )

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
            for line in order_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        videos_by_name = {video.path.name: video for video in videos}
        missing_filenames = [
            filename for filename in listed_filenames if filename not in videos_by_name
        ]
        if missing_filenames:
            raise ValueError(
                f"Order file references missing input video: {missing_filenames[0]}"
            )

        files = tuple(videos_by_name[filename] for filename in listed_filenames)
        listed_filename_set = set(listed_filenames)
        warnings.extend(
            f"order_file_omits_input: {video.path.name}"
            for video in natural_order
            if video.path.name not in listed_filename_set
        )

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
