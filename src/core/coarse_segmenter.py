from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median, pstdev

from src.core.visual_feature_extractor import FrameFeature


@dataclass(frozen=True)
class NodeCandidate:
    node_id: str
    label: str
    start_global_time: float
    end_global_time: float
    duration_seconds: float
    confidence: float
    score: float
    representative_sample_id: str
    representative_image_path: Path
    reason: str


def build_candidate_nodes(
    features: list[FrameFeature],
    min_node_duration_seconds: float,
    sample_interval_seconds: float,
) -> list[NodeCandidate]:
    if not features:
        return []

    threshold = _activity_threshold(features)
    groups = _active_groups(features, threshold)
    if not groups:
        fallback = _fallback_group(features)
        groups = [fallback] if fallback else []

    candidates: list[NodeCandidate] = []
    for group in groups:
        representative = max(group, key=lambda item: item.activity_score)
        start = max(0.0, group[0].time_seconds - sample_interval_seconds)
        end = group[-1].time_seconds + sample_interval_seconds
        if end - start < min_node_duration_seconds:
            end = start + min_node_duration_seconds
        score = max(item.activity_score for item in group)
        confidence = max(0.05, min(0.99, score / max(threshold * 2.0, 0.001)))
        candidates.append(
            NodeCandidate(
                node_id=f"node_{len(candidates) + 1:04d}",
                label=_label_for(representative),
                start_global_time=round(start, 3),
                end_global_time=round(end, 3),
                duration_seconds=round(end - start, 3),
                confidence=round(confidence, 3),
                score=round(score, 6),
                representative_sample_id=representative.sample_id,
                representative_image_path=representative.image_path,
                reason=_reason_for(representative, threshold),
            )
        )
    return candidates


def _activity_threshold(features: list[FrameFeature]) -> float:
    scores = [item.activity_score for item in features if not item.black_frame]
    if not scores:
        return 1.0
    center = median(scores)
    spread = pstdev(scores) if len(scores) > 1 else 0.0
    return max(0.035, min(0.22, center + spread * 0.45))


def _active_groups(
    features: list[FrameFeature],
    threshold: float,
) -> list[list[FrameFeature]]:
    groups: list[list[FrameFeature]] = []
    current: list[FrameFeature] = []
    for feature in features:
        active = not feature.black_frame and feature.activity_score >= threshold
        if active:
            current.append(feature)
            continue
        if current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _fallback_group(features: list[FrameFeature]) -> list[FrameFeature] | None:
    non_black = [item for item in features if not item.black_frame]
    if not non_black:
        return None
    best = max(non_black, key=lambda item: item.activity_score)
    return [best] if best.activity_score > 0 else None


def _label_for(feature: FrameFeature) -> str:
    if feature.black_frame:
        return "blank_or_black"
    if feature.edge_density >= 0.075 and feature.activity_score >= 0.08:
        return "hair_detail"
    if feature.activity_score >= 0.12:
        return "front_hair_strand_pull"
    if feature.diff_score >= 0.05:
        return "zoom_pan_view"
    return "static_low_value"


def _reason_for(feature: FrameFeature, threshold: float) -> str:
    return (
        "activity score "
        f"{feature.activity_score:.3f} crossed threshold {threshold:.3f}; "
        f"diff={feature.diff_score:.3f}, edge_diff={feature.edge_diff_score:.3f}"
    )
