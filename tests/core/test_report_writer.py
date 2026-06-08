import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.core.file_collector import CollectionResult, InputVideo
from src.core.report_writer import (
    dataclass_list,
    write_edit_report_text,
    write_input_order,
    write_json,
)
from src.core.timeline_mapper import TimelineRange
from src.core.video_probe import VideoMetadata


@dataclass(frozen=True)
class ExportRecord:
    path: Path
    note: str


def make_collection(tmp_path: Path) -> CollectionResult:
    input_dir = tmp_path / "input"
    part2 = InputVideo(input_dir / "part2.mp4", 200.0)
    part10 = InputVideo(input_dir / "part10.mp4", 100.0)
    return CollectionResult(
        files=(part2, part10),
        natural_order=(part2, part10),
        modified_time_order=(part10, part2),
        warnings=("filename_and_mtime_order_conflict",),
    )


def make_timeline(tmp_path: Path) -> list[TimelineRange]:
    input_dir = tmp_path / "input"
    return [
        TimelineRange(str(input_dir / "part2.mp4"), 0.0, 12.5, 0.0, 12.5),
        TimelineRange(str(input_dir / "part10.mp4"), 12.5, 30.0, 0.0, 17.5),
    ]


def test_write_json_converts_nested_dataclasses_and_paths_and_preserves_chinese(
    tmp_path: Path,
) -> None:
    output = tmp_path / "nested" / "edit_report.json"
    record = ExportRecord(
        path=tmp_path / "output" / "full_concat.mp4",
        note="基础处理完成",
    )

    write_json(output, {"record": record, "paths": [record.path]})

    text = output.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data == {
        "record": {
            "path": str(record.path),
            "note": "基础处理完成",
        },
        "paths": [str(record.path)],
    }
    assert "基础处理完成" in text
    assert r"\u57fa" not in text


def test_dataclass_list_converts_paths_to_strings() -> None:
    path = Path("output/full_concat.mp4")

    data = dataclass_list([ExportRecord(path, "完成")])

    assert data == [{"path": str(path), "note": "完成"}]


def test_write_input_order_includes_final_orders_warnings_and_timeline(
    tmp_path: Path,
) -> None:
    output = tmp_path / "reports" / "input_order.txt"
    collection = make_collection(tmp_path)
    timeline = make_timeline(tmp_path)

    write_input_order(output, collection, timeline)

    text = output.read_text(encoding="utf-8")
    assert "最终顺序" in text
    assert "自然文件名顺序" in text
    assert "修改时间顺序" in text
    assert "警告" in text
    assert "全局时间线" in text
    final_section = text.split("自然文件名顺序", maxsplit=1)[0]
    assert final_section.index("part2.mp4") < final_section.index("part10.mp4")
    assert re.search(
        r"修改时间顺序[\s\S]*part10\.mp4[\s\S]*part2\.mp4",
        text,
    )
    assert "filename_and_mtime_order_conflict" in text
    assert "0.000s -> 12.500s" in text
    assert "12.500s -> 30.000s" in text


def test_write_edit_report_text_includes_chinese_metadata_and_timeline(
    tmp_path: Path,
) -> None:
    output = tmp_path / "reports" / "edit_report.txt"
    video_path = tmp_path / "input" / "手臂雕刻.mp4"
    metadata = [
        VideoMetadata(
            path=video_path,
            duration_seconds=12.5,
            width=1080,
            height=1920,
            fps=29.97,
            codec="h264",
            has_audio=False,
            modified_time=100.0,
        )
    ]
    timeline = [TimelineRange(str(video_path), 0.0, 12.5, 0.0, 12.5)]

    write_edit_report_text(
        output,
        metadata,
        timeline,
        warnings=["filename_and_mtime_order_conflict"],
    )

    text = output.read_text(encoding="utf-8")
    for expected in (
        "基础处理报告",
        "输入视频",
        "全局时间线",
        "警告",
        "手臂雕刻.mp4",
        "12.500s",
        "1080x1920",
        "29.970fps",
        "h264",
        "0.000s -> 12.500s",
        "filename_and_mtime_order_conflict",
    ):
        assert expected in text
