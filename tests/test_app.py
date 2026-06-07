from __future__ import annotations

from pathlib import Path

import app


def test_build_parser_supports_project_directory(tmp_path: Path) -> None:
    args = app.build_parser().parse_args(["--project-dir", str(tmp_path)])

    assert args.project_dir == tmp_path
