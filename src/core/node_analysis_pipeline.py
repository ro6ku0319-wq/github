from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from src.core.activity_curve import write_activity_curve_png
from src.core.coarse_segmenter import NodeCandidate, build_candidate_nodes
from src.core.contact_sheet_builder import write_node_contact_sheet
from src.core.cut_decision_builder import (
    build_cut_decision_rows,
    write_cut_decision_csv,
    write_operation_score_table_csv,
)
from src.core.frame_sampler import FrameSample, FrameSampler
from src.core.fine_boundary_refiner import FineBoundaryRefiner
from src.core.report_writer import dataclass_list, write_json
from src.core.project_manifest import ProjectManifest
from src.core.visual_feature_extractor import FrameFeature, extract_visual_features


class Sampler(Protocol):
    def sample(
        self,
        source: Path,
        frames_dir: Path,
        interval_seconds: float,
    ) -> list[FrameSample]:
        pass


class BoundaryRefiner(Protocol):
    def refine(
        self,
        source: Path,
        candidates: list[NodeCandidate],
        every_n_frames: int,
        search_window_seconds: float,
        completion_hold_frames: int,
    ) -> list[NodeCandidate]:
        pass


@dataclass(frozen=True)
class NodeAnalysisResult:
    samples: list[FrameSample]
    features: list[FrameFeature]
    candidates: list[NodeCandidate]


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name, {})
    return value if isinstance(value, dict) else {}


class NodeAnalysisPipeline:
    def __init__(
        self,
        project_dir: Path,
        config: dict[str, Any],
        log: Callable[[str], None] | None = None,
        progress: Callable[[int, str], None] | None = None,
        sampler: Sampler | None = None,
        refiner: BoundaryRefiner | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config = config
        self.log = log or (lambda message: None)
        self.progress = progress or (lambda value, message: None)
        self.sampler = sampler or FrameSampler()
        self.refiner = refiner or FineBoundaryRefiner()

    @property
    def output_dir(self) -> Path:
        output = _section(self.config, "output")
        return (self.project_dir / str(output.get("output_dir", "output"))).resolve()

    @property
    def accelerated_base_path(self) -> Path:
        return self.output_dir / "accelerated_base.mp4"

    def run_all(self) -> NodeAnalysisResult:
        source = self.accelerated_base_path
        if not source.exists():
            raise FileNotFoundError(
                f"缺少 {source.name}，请先运行基础处理生成 output/accelerated_base.mp4"
            )

        fine_cut = _section(self.config, "fine_cut")
        interval = float(fine_cut.get("coarse_sample_interval_seconds", 0.4))
        min_node_duration = float(fine_cut.get("min_node_duration_seconds", 0.25))
        completion_hold_frames = int(fine_cut.get("completion_hold_frames", 3))
        fine_enabled = bool(fine_cut.get("enabled", False))
        fine_every_n_frames = int(fine_cut.get("fine_sample_every_n_frames", 2))
        boundary_window = float(
            fine_cut.get("boundary_search_window_seconds", 1.0)
        )

        self._update(5, "准备节点分析")
        frame_cache = self.output_dir / "frame_cache"
        samples = self.sampler.sample(source.resolve(), frame_cache, interval)
        self._write_frame_manifest(source, samples)

        self._update(35, "提取画面变化特征")
        features = extract_visual_features(samples)
        write_operation_score_table_csv(
            self.output_dir / "operation_score_table.csv",
            [_feature_row(item) for item in features],
        )

        self._update(60, "召回候选动作节点")
        candidates = build_candidate_nodes(
            features,
            min_node_duration,
            interval,
            completion_hold_frames=completion_hold_frames,
        )
        if fine_enabled and candidates:
            self._update(70, "逐帧细化动作边界")
            candidates = self.refiner.refine(
                source.resolve(),
                candidates,
                every_n_frames=fine_every_n_frames,
                search_window_seconds=boundary_window,
                completion_hold_frames=completion_hold_frames,
            )
        write_json(
            self.output_dir / "node_analysis.json",
            {
                "source": source,
                "sample_interval_seconds": interval,
                "features": dataclass_list(features),
                "candidates": dataclass_list(candidates),
            },
        )

        self._update(80, "生成 cut_decision.csv")
        operation_priority = _section(self.config, "operation_priority")
        cut_rows = build_cut_decision_rows(candidates, operation_priority)
        write_cut_decision_csv(self.output_dir / "cut_decision.csv", cut_rows)

        self._update(92, "生成节点联系图和活动曲线")
        llm_package = _section(self.config, "llm_package")
        max_items = int(llm_package.get("max_contact_sheet_items_per_page", 60))
        write_node_contact_sheet(
            self.output_dir / "node_contact_sheet.jpg",
            candidates,
            max_items=max_items,
        )
        write_activity_curve_png(self.output_dir / "activity_curve.png", features)

        ProjectManifest(self.project_dir, self.config).refresh()
        self._update(100, "节点分析完成")
        return NodeAnalysisResult(samples=samples, features=features, candidates=candidates)

    def _write_frame_manifest(self, source: Path, samples: list[FrameSample]) -> None:
        write_json(
            self.output_dir / "frame_manifest.json",
            {
                "source": source,
                "samples": dataclass_list(samples),
            },
        )

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)


def _feature_row(feature: FrameFeature) -> dict[str, str]:
    return {
        "sample_id": feature.sample_id,
        "time_seconds": f"{feature.time_seconds:.3f}",
        "brightness": f"{feature.brightness:.6f}",
        "edge_density": f"{feature.edge_density:.6f}",
        "diff_score": f"{feature.diff_score:.6f}",
        "edge_diff_score": f"{feature.edge_diff_score:.6f}",
        "region_change_score": f"{feature.region_change_score:.6f}",
        "activity_score": f"{feature.activity_score:.6f}",
        "black_frame": "true" if feature.black_frame else "false",
        "global_diff_score": f"{feature.global_diff_score:.6f}",
        "center_diff_score": f"{feature.center_diff_score:.6f}",
        "ui_diff_score": f"{feature.ui_diff_score:.6f}",
        "local_change_density": f"{feature.local_change_density:.6f}",
        "brightness_score": f"{feature.brightness_score:.6f}",
        "detail_score": f"{feature.detail_score:.6f}",
        "stability_after_change": f"{feature.stability_after_change:.6f}",
        "novelty_score": f"{feature.novelty_score:.6f}",
        "repetition_score": f"{feature.repetition_score:.6f}",
        "reverted_to_previous_state": (
            "true" if feature.reverted_to_previous_state else "false"
        ),
    }
