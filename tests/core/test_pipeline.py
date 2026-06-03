from pathlib import Path

import pytest

from src.core.file_collector import CollectionResult, InputVideo
from src.core.pipeline import FoundationPipeline
from src.core.timeline_mapper import TimelineRange
from src.core.video_probe import VideoMetadata, VideoProbeError


class FakeProcessor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object, object, object]] = []

    def create_full_concat(
        self,
        videos: list[Path],
        output: Path,
        concat_list: Path,
    ) -> None:
        self.calls.append(("concat", videos, output, concat_list))

    def create_accelerated_base(
        self,
        source: Path,
        output: Path,
        factor: float,
    ) -> None:
        self.calls.append(("accelerate", source, output, factor))


def make_input(path: Path, modified_time: float = 100.0) -> InputVideo:
    return InputVideo(path.resolve(), modified_time)


def make_metadata(path: Path, duration_seconds: float = 10.0) -> VideoMetadata:
    return VideoMetadata(
        path=path.resolve(),
        duration_seconds=duration_seconds,
        width=1080,
        height=1920,
        fps=30.0,
        codec="h264",
        has_audio=False,
        modified_time=100.0,
    )


def make_collection(tmp_path: Path) -> CollectionResult:
    part1 = make_input(tmp_path / "clips" / "part1.mp4", 100.0)
    part2 = make_input(tmp_path / "clips" / "part2.mp4", 200.0)
    return CollectionResult(
        files=(part1, part2),
        natural_order=(part1, part2),
        modified_time_order=(part2, part1),
        warnings=("filename_and_mtime_order_conflict",),
    )


def test_collect_uses_configured_input_directory_and_order_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    collection = make_collection(tmp_path)
    calls: list[tuple[Path, Path]] = []

    def fake_collect_videos(input_dir: Path, order_file: Path) -> CollectionResult:
        calls.append((input_dir, order_file))
        return collection

    monkeypatch.setattr("src.core.pipeline.collect_videos", fake_collect_videos)
    pipeline = FoundationPipeline(
        tmp_path,
        {"input": {"input_dir": "clips", "order_file": "clips/custom_order.txt"}},
        processor=FakeProcessor(),
        tool_validator=lambda: None,
    )

    result = pipeline.collect()

    assert result is collection
    assert calls == [
        (tmp_path.resolve() / "clips", tmp_path.resolve() / "clips" / "custom_order.txt")
    ]


def test_probe_skips_unreadable_videos_and_logs_in_simplified_chinese(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    bad = make_input(tmp_path / "clips" / "broken.mp4")
    good = make_input(tmp_path / "clips" / "part2.mp4")
    logs: list[str] = []

    def fake_probe_video(path: Path) -> VideoMetadata:
        if path == bad.path:
            raise VideoProbeError("ffprobe 输出损坏")
        return make_metadata(path, 12.5)

    monkeypatch.setattr("src.core.pipeline.probe_video", fake_probe_video)
    pipeline = FoundationPipeline(
        tmp_path,
        {},
        log=logs.append,
        processor=FakeProcessor(),
        tool_validator=lambda: None,
    )

    metadata = pipeline.probe((bad, good))

    assert [item.path for item in metadata] == [good.path]
    assert any(
        "跳过无法读取的视频" in message
        and "broken.mp4" in message
        and "ffprobe 输出损坏" in message
        for message in logs
    )


def test_probe_fails_clearly_when_all_inputs_are_unreadable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    inputs = (
        make_input(tmp_path / "clips" / "broken1.mp4"),
        make_input(tmp_path / "clips" / "broken2.mp4"),
    )
    logs: list[str] = []

    def fake_probe_video(path: Path) -> VideoMetadata:
        raise VideoProbeError(f"{path.name} 无法解析")

    monkeypatch.setattr("src.core.pipeline.probe_video", fake_probe_video)
    pipeline = FoundationPipeline(
        tmp_path,
        {},
        log=logs.append,
        processor=FakeProcessor(),
        tool_validator=lambda: None,
    )

    with pytest.raises(RuntimeError, match="所有输入视频都无法读取"):
        pipeline.probe(inputs)

    assert sum("跳过无法读取的视频" in message for message in logs) == 2


def test_run_all_validates_tools_writes_reports_runs_media_and_reports_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    collection = make_collection(tmp_path)
    metadata = [
        make_metadata(collection.files[0].path, 12.5),
        make_metadata(collection.files[1].path, 17.5),
    ]
    timeline = [
        TimelineRange(str(metadata[0].path), 0.0, 12.5, 0.0, 12.5),
        TimelineRange(str(metadata[1].path), 12.5, 30.0, 0.0, 17.5),
    ]
    validated: list[str] = []
    collect_calls: list[tuple[Path, Path]] = []
    probe_calls: list[Path] = []
    build_timeline_calls: list[list[VideoMetadata]] = []
    report_calls: dict[str, object] = {}

    def fake_collect_videos(input_dir: Path, order_file: Path) -> CollectionResult:
        collect_calls.append((input_dir, order_file))
        return collection

    def fake_probe_video(path: Path) -> VideoMetadata:
        probe_calls.append(path)
        return metadata[len(probe_calls) - 1]

    def fake_build_timeline(items: list[VideoMetadata]) -> list[TimelineRange]:
        build_timeline_calls.append(items)
        return timeline

    def fake_write_input_order(
        path: Path,
        collection_arg: CollectionResult,
        timeline_arg: list[TimelineRange],
    ) -> None:
        report_calls["input_order"] = (path, collection_arg, timeline_arg)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("input order", encoding="utf-8")

    def fake_write_json(path: Path, payload: object) -> None:
        report_calls["json"] = (path, payload)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    def fake_write_edit_report_text(
        path: Path,
        metadata_arg: list[VideoMetadata],
        timeline_arg: list[TimelineRange],
        warnings: tuple[str, ...],
    ) -> None:
        report_calls["text"] = (path, metadata_arg, timeline_arg, warnings)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("edit report", encoding="utf-8")

    monkeypatch.setattr("src.core.pipeline.collect_videos", fake_collect_videos)
    monkeypatch.setattr("src.core.pipeline.probe_video", fake_probe_video)
    monkeypatch.setattr("src.core.pipeline.build_timeline", fake_build_timeline)
    monkeypatch.setattr("src.core.pipeline.write_input_order", fake_write_input_order)
    monkeypatch.setattr("src.core.pipeline.write_json", fake_write_json)
    monkeypatch.setattr(
        "src.core.pipeline.write_edit_report_text",
        fake_write_edit_report_text,
    )

    logs: list[str] = []
    progress: list[tuple[int, str]] = []
    processor = FakeProcessor()
    config = {
        "input": {"input_dir": "clips", "order_file": "clips/order.txt"},
        "output": {"output_dir": "rendered"},
        "base_processing": {"acceleration_factor": 6.5},
    }
    pipeline = FoundationPipeline(
        tmp_path,
        config,
        log=logs.append,
        progress=lambda value, message: progress.append((value, message)),
        processor=processor,
        tool_validator=lambda: validated.append("validated"),
    )

    pipeline.run_all()

    output_dir = tmp_path.resolve() / "rendered"
    assert validated == ["validated"]
    assert collect_calls == [
        (tmp_path.resolve() / "clips", tmp_path.resolve() / "clips" / "order.txt")
    ]
    assert probe_calls == [item.path for item in collection.files]
    assert build_timeline_calls == [metadata]
    assert report_calls["input_order"] == (
        output_dir / "input_order.txt",
        collection,
        timeline,
    )
    json_path, json_payload = report_calls["json"]
    assert json_path == output_dir / "edit_report.json"
    assert {"videos", "timeline", "warnings"} <= set(json_payload)
    assert tuple(json_payload["warnings"]) == collection.warnings
    assert report_calls["text"] == (
        output_dir / "edit_report.txt",
        metadata,
        timeline,
        collection.warnings,
    )
    assert (output_dir / "input_order.txt").exists()
    assert (output_dir / "edit_report.json").exists()
    assert (output_dir / "edit_report.txt").exists()
    assert processor.calls == [
        (
            "concat",
            [item.path for item in metadata],
            output_dir / "full_concat.mp4",
            output_dir / "concat_list.txt",
        ),
        (
            "accelerate",
            output_dir / "full_concat.mp4",
            output_dir / "accelerated_base.mp4",
            6.5,
        ),
    ]
    assert [value for value, _message in progress] == sorted(
        value for value, _message in progress
    )
    assert progress[-1][0] == 100
    progress_text = "\n".join(message for _value, message in progress)
    log_text = "\n".join(logs)
    for expected in (
        "扫描输入素材",
        "读取视频元数据",
        "生成 full_concat.mp4",
        "生成 accelerated_base.mp4",
        "基础处理完成",
    ):
        assert expected in progress_text
        assert expected in log_text
    assert "full_concat.mp4" in log_text
    assert "accelerated_base.mp4" in log_text
