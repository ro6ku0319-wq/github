from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class VideoProbeError(ValueError):
    pass


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    duration_seconds: float
    width: int
    height: int
    fps: float
    codec: str
    has_audio: bool
    modified_time: float

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def _payload_error(path: Path, cause: str) -> VideoProbeError:
    return VideoProbeError(f"Malformed ffprobe payload for {path}: {cause}")


def _parse_duration(payload: dict[str, Any], path: Path) -> float:
    format_payload = payload.get("format")
    if not isinstance(format_payload, dict) or "duration" not in format_payload:
        raise _payload_error(path, "missing duration")

    value = format_payload["duration"]
    if isinstance(value, bool):
        raise _payload_error(path, "invalid duration")
    try:
        duration = float(value)
    except (TypeError, ValueError, OverflowError):
        raise _payload_error(path, "invalid duration") from None
    if not math.isfinite(duration) or duration <= 0:
        raise _payload_error(path, "invalid duration")
    return duration


def _parse_rate(value: object, path: Path) -> float:
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise _payload_error(path, "invalid frame rate")
    try:
        rate = float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError, OverflowError):
        raise _payload_error(path, "invalid frame rate") from None
    if not math.isfinite(rate) or rate <= 0:
        raise _payload_error(path, "invalid frame rate")
    return rate


def _parse_positive_int(value: object, field: str, path: Path) -> int:
    if isinstance(value, bool):
        raise _payload_error(path, f"invalid video {field}")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        raise _payload_error(path, f"invalid video {field}") from None
    if parsed <= 0:
        raise _payload_error(path, f"invalid video {field}")
    return parsed


def _find_video_stream(payload: dict[str, Any], path: Path) -> tuple[dict[str, Any], list[Any]]:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        raise _payload_error(path, "missing video stream")
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == "video":
            return stream, streams
    raise _payload_error(path, "missing video stream")


def probe_video(path: Path) -> VideoMetadata:
    source_path = Path(path).resolve()
    modified_time = source_path.stat().st_mtime
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of",
        "json",
        str(source_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        raise _payload_error(source_path, "malformed JSON") from None
    if not isinstance(payload, dict):
        raise _payload_error(source_path, "expected JSON object")

    video, streams = _find_video_stream(payload, source_path)
    codec = video.get("codec_name")
    if not isinstance(codec, str) or not codec:
        raise _payload_error(source_path, "invalid video codec")

    return VideoMetadata(
        path=source_path,
        duration_seconds=_parse_duration(payload, source_path),
        width=_parse_positive_int(video.get("width"), "width", source_path),
        height=_parse_positive_int(video.get("height"), "height", source_path),
        fps=_parse_rate(video.get("r_frame_rate"), source_path),
        codec=codec,
        has_audio=any(
            isinstance(stream, dict) and stream.get("codec_type") == "audio"
            for stream in streams
        ),
        modified_time=modified_time,
    )
