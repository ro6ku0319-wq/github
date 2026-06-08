from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


def _json_ready(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(value)
    raise TypeError(f"无法序列化 JSON 值: {type(value).__name__}")


def _names(items: Any) -> str:
    return ", ".join(item.path.name for item in items)


def _warnings_text(warnings: Any) -> str:
    return ", ".join(warnings) if warnings else "无"


def write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _json_ready(payload),
            ensure_ascii=False,
            indent=2,
            default=_json_default,
        ),
        encoding="utf-8",
    )


def dataclass_list(items: Any) -> list[dict[str, Any]]:
    return [_json_ready(item) for item in items]


def write_input_order(path: Path, collection: Any, timeline: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["最终顺序:"]
    lines.extend(f"- {item.path.name}" for item in collection.files)
    lines.extend(
        [
            "",
            "自然文件名顺序: " + _names(collection.natural_order),
            "修改时间顺序: " + _names(collection.modified_time_order),
            "警告: " + _warnings_text(collection.warnings),
            "",
            "全局时间线:",
        ]
    )
    lines.extend(
        f"- {item.source_file}: {item.global_start:.3f}s -> {item.global_end:.3f}s"
        for item in timeline
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_edit_report_text(
    path: Path,
    metadata: Any,
    timeline: Any,
    warnings: Any,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["OB11 ZBrush Body Cut 基础处理报告", "", "输入视频:"]
    lines.extend(
        (
            f"- {item.path.name}: {item.duration_seconds:.3f}s, "
            f"{item.resolution}, {item.fps:.3f}fps, {item.codec}"
        )
        for item in metadata
    )
    lines.extend(["", "全局时间线:"])
    lines.extend(
        f"- {item.source_file}: {item.global_start:.3f}s -> {item.global_end:.3f}s"
        for item in timeline
    )
    lines.extend(["", "警告: " + _warnings_text(warnings)])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
