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

HAIR_REGION_KEYS = (
    "front_hair",
    "sideburns",
    "back_hair",
    "other_hair_blocks",
)
ALLOWED_HAIR_REGIONS = {*HAIR_REGION_KEYS, "not_hair"}
ALLOWED_PROCESS_PHASES = {"blockout", "refinement", "other"}
ALLOWED_SYMMETRY_SIDES = {
    "left",
    "right",
    "center",
    "both",
    "not_applicable",
    "unknown",
}
ALLOWED_SYMMETRY_KEEP_ROLES = {
    "representative",
    "duplicate_omitted",
    "not_symmetric",
    "supporting_context",
    "unknown",
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
    target_duration = _number(
        payload.get("recommended_body_duration_seconds"),
        "recommended_body_duration_seconds",
    )
    if target_duration != 60:
        warnings.append(
            "warning: recommended_body_duration_seconds 必须保持为 60"
        )
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
    for index, segment in enumerate(segments):
        _validate_optional_hair_fields(segment, index, warnings)

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
    _append_body_60_duration_warning(segments, warnings)
    _validate_hair_coverage(payload, segments, warnings)
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


def _validate_optional_hair_fields(
    segment: dict[str, Any],
    index: int,
    warnings: list[str],
) -> None:
    hair_region = segment.get("hair_region")
    if hair_region is not None and hair_region not in ALLOWED_HAIR_REGIONS:
        raise LlmDecisionValidationError(
            f"segments[{index}].hair_region 无效: {hair_region}"
        )
    process_phase = segment.get("process_phase")
    if process_phase is not None and process_phase not in ALLOWED_PROCESS_PHASES:
        raise LlmDecisionValidationError(
            f"segments[{index}].process_phase 无效: {process_phase}"
        )
    shows_phase_result = segment.get("shows_phase_result")
    if shows_phase_result is not None and not isinstance(shows_phase_result, bool):
        raise LlmDecisionValidationError(
            f"segments[{index}].shows_phase_result 必须是 JSON 布尔值"
        )
    if "importance" in segment:
        importance = _number(segment["importance"], f"segments[{index}].importance")
        if importance < 0 or importance > 10:
            warnings.append(f"warning: segments[{index}].importance 超出 0-10")
    _validate_optional_symmetry_fields(segment, index, warnings)


def _validate_optional_symmetry_fields(
    segment: dict[str, Any],
    index: int,
    warnings: list[str],
) -> None:
    symmetry_group = segment.get("symmetry_group")
    if symmetry_group is not None and not isinstance(symmetry_group, str):
        raise LlmDecisionValidationError(
            f"segments[{index}].symmetry_group 必须是字符串"
        )
    symmetry_side = segment.get("symmetry_side")
    if symmetry_side is not None and symmetry_side not in ALLOWED_SYMMETRY_SIDES:
        raise LlmDecisionValidationError(
            f"segments[{index}].symmetry_side 无效: {symmetry_side}"
        )
    symmetry_keep_role = segment.get("symmetry_keep_role")
    if (
        symmetry_keep_role is not None
        and symmetry_keep_role not in ALLOWED_SYMMETRY_KEEP_ROLES
    ):
        raise LlmDecisionValidationError(
            f"segments[{index}].symmetry_keep_role 无效: {symmetry_keep_role}"
        )
    if (
        symmetry_keep_role == "duplicate_omitted"
        and segment.get("include_in_body_60s") is True
        and normalise_edit_action(segment.get("edit_action")) != "delete"
    ):
        warnings.append(
            f"warning: segments[{index}] symmetry_keep_role=duplicate_omitted "
            "但仍被 include_in_body_60s 选中"
        )
    if (
        symmetry_keep_role == "representative"
        and segment.get("include_in_body_60s") is not True
    ):
        warnings.append(
            f"warning: segments[{index}] symmetry_keep_role=representative "
            "但未进入 body_60"
        )


def _append_body_60_duration_warning(
    segments: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    total = sum(
        _number(segment.get("output_duration_seconds", 0), "output_duration_seconds")
        for segment in segments
        if segment.get("include_in_body_60s") is True
        and normalise_edit_action(segment.get("edit_action")) != "delete"
    )
    if total < 55 or total > 65:
        warnings.append(
            f"warning: body_60_total_duration={total:.3f}s，应压缩到约 60 秒"
        )


def _validate_hair_coverage(
    payload: dict[str, Any],
    segments: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    presence = payload.get("hair_region_presence")
    if presence is None:
        warnings.append(
            "warning: 缺少 hair_region_presence，无法校验四块头发的大型/细化结果覆盖"
        )
        return
    if not isinstance(presence, dict):
        raise LlmDecisionValidationError("hair_region_presence 必须是对象")

    missing_coverage: list[str] = []
    for region in HAIR_REGION_KEYS:
        if region not in presence:
            missing_coverage.append(f"hair_region_presence.{region}")
            continue
        if not isinstance(presence[region], bool):
            raise LlmDecisionValidationError(
                f"hair_region_presence.{region} 必须是 JSON 布尔值"
            )
        if not presence[region]:
            continue
        for phase in ("blockout", "refinement"):
            covered = any(
                segment.get("include_in_body_60s") is True
                and normalise_edit_action(segment.get("edit_action")) != "delete"
                and segment.get("hair_region") == region
                and segment.get("process_phase") == phase
                and segment.get("shows_phase_result") is True
                for segment in segments
            )
            if not covered:
                missing_coverage.append(f"{region}/{phase}")
    if missing_coverage:
        raise LlmDecisionValidationError(
            "body_60 缺少必须展示的头发区域/阶段结果: "
            + ", ".join(missing_coverage)
        )


def _number(value: object, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise LlmDecisionValidationError(f"{field} 必须是数字") from error
