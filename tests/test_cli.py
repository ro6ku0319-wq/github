from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_cli_module():
    return importlib.import_module("make_timelapse")


def patch_cli_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    cli_module,
    calls: list[object],
) -> None:
    config = {"output": {"logs_dir": "自定义日志"}}

    class FakeConfigManager:
        def __init__(self, project_dir: Path) -> None:
            self.project_dir = Path(project_dir)
            calls.append(("config_manager", self.project_dir))

        def load(self) -> dict[str, object]:
            calls.append(("load_config", self.project_dir))
            return config

    class FakeProjectLogger:
        def __init__(self, logs_dir: Path, *args: object, **kwargs: object) -> None:
            self.logs_dir = Path(logs_dir)
            calls.append(("logger", self.logs_dir))

        def __call__(self, message: str) -> None:
            calls.append(("log", message))

    class FakeFoundationPipeline:
        def __init__(
            self,
            project_dir: Path,
            config_arg: dict[str, object],
            log: FakeProjectLogger,
        ) -> None:
            self.collection = SimpleNamespace(files=["part1.mp4", "part2.mp4"])
            self.metadata = ["metadata1", "metadata2"]
            calls.append(("pipeline", Path(project_dir), config_arg, log))

        def run_all(self) -> None:
            calls.append("run_all")

        def collect(self):
            calls.append("collect")
            return self.collection

        def probe(self, files: list[str]) -> list[str]:
            calls.append("probe")
            assert files is self.collection.files
            return self.metadata

        def create_full_concat(self, metadata: list[str]) -> None:
            calls.append("concat")
            assert metadata is self.metadata

        def create_accelerated_base(self) -> None:
            calls.append("accelerate")

    monkeypatch.setattr(cli_module, "ConfigManager", FakeConfigManager)
    monkeypatch.setattr(cli_module, "ProjectLogger", FakeProjectLogger)
    monkeypatch.setattr(cli_module, "FoundationPipeline", FakeFoundationPipeline)


def stage_calls(calls: list[object]) -> list[str]:
    return [call for call in calls if isinstance(call, str)]


def test_build_parser_supports_project_dir_and_foundation_stage_switches(
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    parser = cli.build_parser()
    project_dir = tmp_path / "项目"

    args = parser.parse_args(
        [
            "--project-dir",
            str(project_dir),
            "--run-foundation",
            "--only-full-concat",
            "--only-accelerate",
        ]
    )

    assert args.project_dir == project_dir
    assert args.run_foundation is True
    assert args.only_full_concat is True
    assert args.only_accelerate is True


def test_main_loads_configures_logger_and_runs_foundation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--run-foundation"])

    assert result == 0
    assert calls[0] == ("config_manager", tmp_path)
    assert calls[1] == ("load_config", tmp_path)
    assert calls[2] == ("logger", tmp_path / "自定义日志")
    assert calls[3][0] == "pipeline"
    assert calls[4] == "run_all"


def test_main_only_full_concat_collects_probes_and_concats(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--only-full-concat"])

    assert result == 0
    assert stage_calls(calls) == ["collect", "probe", "concat"]


def test_main_only_accelerate_runs_accelerated_base_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--only-accelerate"])

    assert result == 0
    assert stage_calls(calls) == ["accelerate"]


def test_main_without_stage_exits_with_clear_simplified_chinese_message(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--project-dir", str(tmp_path)])

    message = str(exc_info.value)
    assert "请选择" in message
    assert "--run-foundation" in message
    assert "GUI" in message
    assert "python app.py" in message
