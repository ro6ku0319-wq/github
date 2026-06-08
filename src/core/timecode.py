from __future__ import annotations

import re


TIMECODE_PATTERN = re.compile(r"^(?P<hours>\d{2}):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d(?:\.\d+)?)$")


def parse_timecode(value: object) -> float:
    if isinstance(value, bool):
        raise ValueError(f"无效时间码: {value}")
    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds < 0:
            raise ValueError(f"无效时间码: {value}")
        return seconds
    if not isinstance(value, str):
        raise ValueError(f"无效时间码: {value}")
    match = TIMECODE_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"无效时间码: {value}")
    return (
        int(match.group("hours")) * 3600
        + int(match.group("minutes")) * 60
        + float(match.group("seconds"))
    )


def format_timecode(seconds: float, decimals: int = 1) -> str:
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60
    width = 2 + (1 + decimals if decimals else 0)
    return f"{hours:02d}:{minutes:02d}:{remaining:0{width}.{decimals}f}"
