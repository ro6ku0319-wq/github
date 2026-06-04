from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from src.core.config_manager import ConfigManager
from src.core.logging_setup import ProjectLogger
from src.core.pipeline import FoundationPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OB11 ZBrush body cut 调试入口")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--run-foundation", action="store_true")
    parser.add_argument("--only-full-concat", action="store_true")
    parser.add_argument("--only-accelerate", action="store_true")
    return parser


def _logs_dir(project_dir: Path, config: dict) -> Path:
    output_config = config.get("output", {})
    if not isinstance(output_config, dict):
        output_config = {}
    return project_dir / str(output_config.get("logs_dir", "logs"))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = ConfigManager(args.project_dir)
    config = manager.load()
    logger = ProjectLogger(_logs_dir(args.project_dir, config), sink=print)
    pipeline = FoundationPipeline(args.project_dir, config, log=logger)

    if args.run_foundation:
        pipeline.run_all()
        return 0
    if args.only_full_concat:
        pipeline.create_full_concat(pipeline.probe(pipeline.collect().files))
        return 0
    if args.only_accelerate:
        pipeline.create_accelerated_base()
        return 0

    raise SystemExit(
        "请选择 --run-foundation。日常建议使用 GUI: python app.py"
    )


if __name__ == "__main__":
    raise SystemExit(main())
