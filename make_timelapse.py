from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Sequence

from src.core.config_manager import ConfigManager
from src.core.codex_decision_pipeline import CodexDecisionPipeline
from src.core.editing_profile import EditingProfileManager
from src.core.hook_pipeline import HookPipeline
from src.core.llm_decision_pipeline import LlmDecisionPipeline
from src.core.llm_package_builder import LlmPackageBuilder
from src.core.logging_setup import ProjectLogger
from src.core.node_analysis_pipeline import NodeAnalysisPipeline
from src.core.pipeline import FoundationPipeline
from src.core.review_export_pipeline import ReviewExportPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OB11 ZBrush body cut 调试入口")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    stages = parser.add_mutually_exclusive_group()
    stages.add_argument("--run-foundation", action="store_true")
    stages.add_argument("--only-full-concat", action="store_true")
    stages.add_argument("--only-accelerate", action="store_true")
    stages.add_argument("--analyze-nodes", action="store_true")
    stages.add_argument("--export-cuts", action="store_true")
    stages.add_argument("--build-llm-package", action="store_true")
    stages.add_argument("--codex-generate-decision", action="store_true")
    stages.add_argument("--apply-llm-decision", type=Path)
    stages.add_argument("--confirm-llm-decision", action="store_true")
    stages.add_argument("--export-editing-profile", type=Path)
    stages.add_argument("--import-editing-profile", type=Path)
    stages.add_argument("--export-with-hook", action="store_true")
    stages.add_argument("--use-cut-decision", type=Path)
    stages.add_argument("--generate-body-45", action="store_true")
    stages.add_argument("--generate-body-60", action="store_true")
    stages.add_argument("--generate-body-120", action="store_true")
    return parser


def _logs_dir(project_dir: Path, config: dict) -> Path:
    output_config = config.get("output", {})
    if not isinstance(output_config, dict):
        output_config = {}
    return project_dir / str(output_config.get("logs_dir", "logs"))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (
        args.run_foundation
        or args.only_full_concat
        or args.only_accelerate
        or args.analyze_nodes
        or args.export_cuts
        or args.build_llm_package
        or args.codex_generate_decision
        or args.apply_llm_decision is not None
        or args.confirm_llm_decision
        or args.export_editing_profile is not None
        or args.import_editing_profile is not None
        or args.export_with_hook
        or args.use_cut_decision is not None
        or args.generate_body_45
        or args.generate_body_60
        or args.generate_body_120
    ):
        raise SystemExit(
            "请选择 --run-foundation、--analyze-nodes、--export-cuts、"
            "--build-llm-package、--apply-llm-decision 或 --export-with-hook。"
            "日常建议使用 GUI: python app.py"
        )

    manager = ConfigManager(args.project_dir)
    config = manager.load()
    logger = ProjectLogger(_logs_dir(args.project_dir, config), sink=print)
    if args.export_editing_profile is not None:
        EditingProfileManager().export_archive(args.export_editing_profile)
        return 0
    if args.import_editing_profile is not None:
        EditingProfileManager().import_archive(args.import_editing_profile)
        return 0
    if args.analyze_nodes:
        NodeAnalysisPipeline(args.project_dir, config, log=logger).run_all()
        return 0
    if args.export_cuts:
        ReviewExportPipeline(args.project_dir, config, log=logger).run_all()
        return 0
    if args.use_cut_decision is not None:
        output_config = config.get("output", {})
        if not isinstance(output_config, dict):
            output_config = {}
        destination = args.project_dir / str(
            output_config.get("output_dir", "output")
        ) / "cut_decision.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if args.use_cut_decision.resolve() != destination.resolve():
            shutil.copy2(args.use_cut_decision, destination)
        ReviewExportPipeline(args.project_dir, config, log=logger).run_all()
        return 0
    selected_version = next(
        (
            name
            for enabled, name in (
                (args.generate_body_45, "body_45s"),
                (args.generate_body_60, "body_60s"),
                (args.generate_body_120, "body_120s"),
            )
            if enabled
        ),
        None,
    )
    if selected_version is not None:
        versions = config.get("cut_versions", {})
        if not isinstance(versions, dict):
            versions = {}
        for name in ("body_45s", "body_60s", "body_120s"):
            section = versions.get(name, {})
            if not isinstance(section, dict):
                section = {}
            section["enabled"] = name == selected_version
            versions[name] = section
        config["cut_versions"] = versions
        ReviewExportPipeline(args.project_dir, config, log=logger).run_all()
        return 0
    if args.build_llm_package:
        LlmPackageBuilder(args.project_dir, config, log=logger).build()
        return 0
    if args.codex_generate_decision:
        CodexDecisionPipeline(args.project_dir, config, log=logger).generate()
        return 0
    if args.apply_llm_decision is not None:
        LlmDecisionPipeline(args.project_dir, config, log=logger).apply(
            args.apply_llm_decision
        )
        return 0
    if args.confirm_llm_decision:
        output_config = config.get("output", {})
        if not isinstance(output_config, dict):
            output_config = {}
        project_config = config.get("project", {})
        if not isinstance(project_config, dict):
            project_config = {}
        result_dir = args.project_dir / str(
            output_config.get("output_dir", "output")
        ) / "llm_result"
        EditingProfileManager().confirm_decision(
            result_dir / "codex_generated_edit_decision.json",
            result_dir / "edit_decision.json",
            project_name=str(project_config.get("name", args.project_dir.name)),
        )
        return 0
    if args.export_with_hook:
        HookPipeline(args.project_dir, config, log=logger).run_all()
        return 0

    pipeline = FoundationPipeline(args.project_dir, config, log=logger)

    if args.run_foundation:
        pipeline.run_all()
        return 0
    if args.only_full_concat:
        pipeline.tool_validator()
        pipeline.create_full_concat(pipeline.probe(pipeline.collect().files))
        return 0
    if args.only_accelerate:
        pipeline.tool_validator()
        pipeline.create_accelerated_base()
        return 0
    raise AssertionError("unreachable stage dispatch")


if __name__ == "__main__":
    raise SystemExit(main())
