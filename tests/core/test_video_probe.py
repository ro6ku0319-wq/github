import json
import os
from dataclasses import FrozenInstanceError
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from src.core.video_probe import VideoMetadata, VideoProbeError, probe_video


def assert_no_exposed_internal_context(error: VideoProbeError) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None or error.__suppress_context__


def create_video(path: Path, modified_time: float = 100.0) -> None:
    path.write_bytes(b"video")
    os.utime(path, (modified_time, modified_time))


def valid_payload(*, include_audio: bool = True) -> dict[str, object]:
    streams: list[dict[str, object]] = [
        {
            "codec_type": "video",
            "width": 1920,
            "height": 1080,
            "r_frame_rate": "30/1",
            "codec_name": "h264",
        },
    ]
    if include_audio:
        streams.append({"codec_type": "audio", "codec_name": "aac"})
    return {"format": {"duration": "42.5"}, "streams": streams}


def mock_ffprobe(
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
) -> list[tuple[list[str], dict[str, object]]]:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        calls.append((command, kwargs))
        return CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr("src.core.video_probe.subprocess.run", run)
    return calls


def test_probe_video_normalizes_ffprobe_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video = tmp_path / "part1.mp4"
    create_video(video, modified_time=123.0)
    calls = mock_ffprobe(monkeypatch, json.dumps(valid_payload()))

    metadata = probe_video(video)

    assert metadata.path == video.resolve()
    assert metadata.duration_seconds == 42.5
    assert metadata.resolution == "1920x1080"
    assert metadata.fps == 30.0
    assert metadata.codec == "h264"
    assert metadata.has_audio is True
    assert metadata.modified_time == 123.0
    assert calls == [
        (
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
                "-of",
                "json",
                str(video.resolve()),
            ],
            {"capture_output": True, "text": True, "check": True},
        )
    ]


def test_probe_video_reports_absent_audio_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video = tmp_path / "silent.mp4"
    create_video(video)
    mock_ffprobe(monkeypatch, json.dumps(valid_payload(include_audio=False)))

    metadata = probe_video(video)

    assert metadata.has_audio is False


def test_video_metadata_is_immutable(tmp_path: Path) -> None:
    metadata = VideoMetadata(
        path=tmp_path / "part1.mp4",
        duration_seconds=42.5,
        width=1920,
        height=1080,
        fps=30.0,
        codec="h264",
        has_audio=True,
        modified_time=100.0,
    )

    with pytest.raises(FrozenInstanceError):
        metadata.duration_seconds = 10.0


def test_video_probe_error_is_a_standard_runtime_or_value_error() -> None:
    assert issubclass(VideoProbeError, (ValueError, RuntimeError))


def test_probe_video_rejects_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video = tmp_path / "broken.mp4"
    create_video(video)
    mock_ffprobe(monkeypatch, "{not-json")

    with pytest.raises(
        VideoProbeError,
        match=r"broken\.mp4.*malformed JSON",
    ) as exc_info:
        probe_video(video)

    assert_no_exposed_internal_context(exc_info.value)


def test_probe_video_rejects_missing_video_stream(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video = tmp_path / "audio-only.mp4"
    create_video(video)
    payload = {
        "format": {"duration": "42.5"},
        "streams": [{"codec_type": "audio", "codec_name": "aac"}],
    }
    mock_ffprobe(monkeypatch, json.dumps(payload))

    with pytest.raises(VideoProbeError, match=r"audio-only\.mp4.*missing video stream"):
        probe_video(video)


@pytest.mark.parametrize(
    ("duration", "cause"),
    [
        (None, "missing duration"),
        ("not-a-duration", "invalid duration"),
        ("0", "invalid duration"),
        ("-1", "invalid duration"),
    ],
)
def test_probe_video_rejects_missing_or_invalid_duration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    duration: str | None,
    cause: str,
) -> None:
    video = tmp_path / "bad-duration.mp4"
    create_video(video)
    payload = valid_payload()
    if duration is None:
        del payload["format"]["duration"]  # type: ignore[index]
    else:
        payload["format"]["duration"] = duration  # type: ignore[index]
    mock_ffprobe(monkeypatch, json.dumps(payload))

    with pytest.raises(
        VideoProbeError,
        match=rf"bad-duration\.mp4.*{cause}",
    ) as exc_info:
        probe_video(video)

    assert_no_exposed_internal_context(exc_info.value)


@pytest.mark.parametrize("rate", ["30/0", "not-a-rate", "0/1"])
def test_probe_video_rejects_zero_denominator_or_invalid_frame_rate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rate: str,
) -> None:
    video = tmp_path / "bad-rate.mp4"
    create_video(video)
    payload = valid_payload()
    payload["streams"][0]["r_frame_rate"] = rate  # type: ignore[index]
    mock_ffprobe(monkeypatch, json.dumps(payload))

    with pytest.raises(
        VideoProbeError,
        match=r"bad-rate\.mp4.*invalid frame rate",
    ) as exc_info:
        probe_video(video)

    assert_no_exposed_internal_context(exc_info.value)
