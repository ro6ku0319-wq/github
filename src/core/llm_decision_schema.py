from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.core.timecode import parse_timecode


class LlmDecisionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class LlmDecisionValidationResult:
    payload: dict[str, Any]
    warnings: list[str]


TOP_LEVEL_REQUIRED = {
    "video_type",
    "external_hook",
    "recommended_body_duration_seconds",
    "first_20_seconds_body_plan",
    "segments",
    "cover_candidates",
    "davinci_markers",
    "notes_for_human_editor",
}

SEGMENT_REQUIRED = {
    "node_id",
    "label",
    "label_cn",
    "start_global_time",
    "end_global_time",
    "edit_action",
    "include_in_body_45s",
    "include_in_body_60s",
    "include_in_body_120s",
    "output_duration_seconds",
    "speed_multiplier",
    "rhythm_role",
    "requires_final_position",
    "result_visible_at_next_node",
    "reason",
}

SEGMENT_BOOLEAN_FIELDS = {
    "include_in_body_45s",
    "include_in_body_60s",
    "include_in_body_120s",
    "requires_final_position",
    "result_visible_at_next_node",
}

ALLOWED_ACTIONS = {
    "keep",
    "keep_compress",
    "delete",
    "use_as_transition",
    "keep_until_action_completion",
}

ACTION_ALIASES = {
    "keep_trim_to_candidate_range": "keep",
    "keep_candidate_range": "keep",
    "trim_to_candidate_range": "keep",
    "keep_speedup_inside_candidate_range": "keep_compress",
    "speedup_inside_candidate_range": "keep_compress",
    "keep_as_transition": "use_as_transition",
}


def validate_llm_decision(
    payload: dict[str, Any],
    known_node_ids: set[str],
) -> LlmDecisionValidationResult:
    if not isinstance(payload, dict):
        raise LlmDecisionValidationError("edit_decision.json 顶层必须是对象")
    missing = sorted(TOP_LEVEL_REQUIRED - set(payload))
    if missing:
        raise LlmDecisionValidationError("缺少字段: " + ", ".join(missing))
    segments = payload["segments"]
    if not isinstance(segments, list):
        raise LlmDecisionValidationError("segments 必须是数组")

    warnings: list[str] = []
    if payload.get("video_type") != "body_cut_only":
        warnings.append("warning: video_type 不是 body_cut_only")
    if not payload.get("first_20_seconds_body_plan"):
        warnings.append("warning: first_20_seconds_body_plan 为空")
    elif len(payload["first_20_seconds_body_plan"]) < 2:
        warnings.append("warning: first_20_seconds_body_plan 少于 2 个变化计划")

    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise LlmDecisionValidationError(f"segments[{index}] 必须是对象")
        missing_segment = sorted(SEGMENT_REQUIRED - set(segment))
        if missing_segment:
            raise LlmDecisionValidationError(
                f"segments[{index}] 缺少字段: " + ", ".join(missing_segment)
            )
        action = normalise_edit_action(segment["edit_action"])
        if action not in ALLOWED_ACTIONS:
            raise LlmDecisionValidationError(
                f"segments[{index}] edit_action 无效: {segment['edit_action']}"
            )
        try:
            start = parse_timecode(segment["start_global_time"])
            end = parse_timecode(segment["end_global_time"])
        except ValueError as error:
            raise LlmDecisionValidationError(
                f"segments[{index}] 时间码格式错误: {error}"
            ) from error
        if end <= start:
            raise LlmDecisionValidationError(f"segments[{index}] 结束时间必须大于开始时间")
        for field in SEGMENT_BOOLEAN_FIELDS:
            if not isinstance(segment[field], bool):
                raise LlmDecisionValidationError(
                    f"segments[{index}].{field} 必须是 JSON 布尔值"
                )
        node_id = _normalise_node_id(segment["node_id"])
        if node_id not in known_node_ids:
            warnings.append(f"warning: node_id 不存在: {node_id}")
        speed = _number(segment["speed_multiplier"], f"segments[{index}].speed_multiplier")
        output_duration = _number(
            segment["output_duration_seconds"],
            f"segments[{index}].output_duration_seconds",
        )
        if speed < 0.1 or speed > 100:
            warnings.append(f"warning: segments[{index}] speed_multiplier 超出 0.1–100")
        if action == "keep" and output_duration == 0:
            warnings.append(
                f"warning: segments[{index}] edit_action=keep 但 output_duration_seconds=0"
            )
    for index, marker in enumerate(payload["davinci_markers"]):
        if not isinstance(marker, dict):
            raise LlmDecisionValidationError(f"davinci_markers[{index}] 必须是对象")
        value = marker.get("time")
        if value not in (None, ""):
            try:
                parse_timecode(value)
            except ValueError as error:
                raise LlmDecisionValidationError(
                    f"davinci_markers[{index}] 时间码格式错误: {error}"
                ) from error
    return LlmDecisionValidationResult(payload=payload, warnings=warnings)


def normalise_node_id(value: object) -> str:
    return _normalise_node_id(value)


def normalise_edit_action(value: object) -> str:
    action = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    explicit = ACTION_ALIASES.get(action)
    if explicit is not None:
        return explicit
    if action.startswith("keep_"):
        if "transition" in action:
            return "use_as_transition"
        if "speedup" in action or "compress" in action:
            return "keep_compress"
        return "keep"
    return action


def _normalise_node_id(value: object) -> str:
    if isinstance(value, int):
        return f"node_{value:04d}"
    text = str(value)
    if text.isdigit():
        return f"node_{int(text):04d}"
    return text


def _number(value: object, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise LlmDecisionValidationError(f"{field} 必须是数字") from error
