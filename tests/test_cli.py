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
            self.tool_validator = lambda: calls.append("validate_tools")
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

    class FakeNodeAnalysisPipeline:
        def __init__(
            self,
            project_dir: Path,
            config_arg: dict[str, object],
            log: FakeProjectLogger,
        ) -> None:
            calls.append(("node_pipeline", Path(project_dir), config_arg, log))

        def run_all(self) -> None:
            calls.append("analyze_nodes")

    monkeypatch.setattr(cli_module, "NodeAnalysisPipeline", FakeNodeAnalysisPipeline)

    class FakeReviewExportPipeline:
        def __init__(
            self,
            project_dir: Path,
            config_arg: dict[str, object],
            log: FakeProjectLogger,
        ) -> None:
            calls.append(("export_pipeline", Path(project_dir), config_arg, log))

        def run_all(self) -> None:
            calls.append("export_cuts")

    monkeypatch.setattr(cli_module, "ReviewExportPipeline", FakeReviewExportPipeline)

    class FakeLlmPackageBuilder:
        def __init__(
            self,
            project_dir: Path,
            config_arg: dict[str, object],
            log: FakeProjectLogger,
        ) -> None:
            calls.append(("llm_package", Path(project_dir), config_arg, log))

        def build(self) -> None:
            calls.append("build_llm_package")

    class FakeLlmDecisionPipeline:
        def __init__(
            self,
            project_dir: Path,
            config_arg: dict[str, object],
            log: FakeProjectLogger,
        ) -> None:
            calls.append(("llm_decision", Path(project_dir), config_arg, log))

        def apply(self, path: Path) -> None:
            calls.append(("apply_llm_decision", path))

    monkeypatch.setattr(cli_module, "LlmPackageBuilder", FakeLlmPackageBuilder)
    monkeypatch.setattr(cli_module, "LlmDecisionPipeline", FakeLlmDecisionPipeline)

    class FakeHookPipeline:
        def __init__(
            self,
            project_dir: Path,
            config_arg: dict[str, object],
            log: FakeProjectLogger,
        ) -> None:
            calls.append(("hook_pipeline", Path(project_dir), config_arg, log))

        def run_all(self) -> None:
            calls.append("export_with_hook")

    monkeypatch.setattr(cli_module, "HookPipeline", FakeHookPipeline)


def stage_calls(calls: list[object]) -> list[str]:
    return [call for call in calls if isinstance(call, str)]


@pytest.mark.parametrize(
    ("switch", "attribute"),
    [
        ("--run-foundation", "run_foundation"),
        ("--only-full-concat", "only_full_concat"),
        ("--only-accelerate", "only_accelerate"),
        ("--analyze-nodes", "analyze_nodes"),
        ("--export-cuts", "export_cuts"),
        ("--build-llm-package", "build_llm_package"),
        ("--export-with-hook", "export_with_hook"),
        ("--generate-body-45", "generate_body_45"),
        ("--generate-body-60", "generate_body_60"),
        ("--generate-body-120", "generate_body_120"),
    ],
)
def test_build_parser_supports_project_dir_and_foundation_stage_switches(
    tmp_path: Path,
    switch: str,
    attribute: str,
) -> None:
    cli = load_cli_module()
    parser = cli.build_parser()
    project_dir = tmp_path / "项目"

    args = parser.parse_args(
        [
            "--project-dir",
            str(project_dir),
            switch,
        ]
    )

    assert args.project_dir == project_dir
    assert getattr(args, attribute) is True


def test_build_parser_rejects_conflicting_stage_switches() -> None:
    cli = load_cli_module()
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--only-full-concat", "--only-accelerate"])


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
    assert stage_calls(calls) == ["validate_tools", "collect", "probe", "concat"]


def test_main_only_accelerate_runs_accelerated_base_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--only-accelerate"])

    assert result == 0
    assert stage_calls(calls) == ["validate_tools", "accelerate"]


def test_main_analyze_nodes_runs_node_analysis_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--analyze-nodes"])

    assert result == 0
    assert calls[3][0] == "node_pipeline"
    assert calls[4] == "analyze_nodes"


def test_main_export_cuts_runs_review_export_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--export-cuts"])

    assert result == 0
    assert calls[3][0] == "export_pipeline"
    assert calls[4] == "export_cuts"


def test_main_build_llm_package_runs_package_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--build-llm-package"])

    assert result == 0
    assert calls[3][0] == "llm_package"
    assert calls[4] == "build_llm_package"


def test_main_apply_llm_decision_runs_decision_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)
    decision_path = tmp_path / "output" / "llm_result" / "edit_decision.json"

    result = cli.main(
        [
            "--project-dir",
            str(tmp_path),
            "--apply-llm-decision",
            str(decision_path),
        ]
    )

    assert result == 0
    assert calls[3][0] == "llm_decision"
    assert calls[4] == ("apply_llm_decision", decision_path)


def test_main_export_with_hook_runs_hook_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), "--export-with-hook"])

    assert result == 0
    assert calls[3][0] == "hook_pipeline"
    assert calls[4] == "export_with_hook"


@pytest.mark.parametrize(
    ("switch", "selected"),
    [
        ("--generate-body-45", "body_45s"),
        ("--generate-body-60", "body_60s"),
        ("--generate-body-120", "body_120s"),
    ],
)
def test_main_generate_single_body_version_runs_only_selected_export(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    switch: str,
    selected: str,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)

    result = cli.main(["--project-dir", str(tmp_path), switch])

    assert result == 0
    export_call = next(call for call in calls if isinstance(call, tuple) and call[0] == "export_pipeline")
    config = export_call[2]
    assert config["cut_versions"][selected]["enabled"] is True
    assert sum(
        section["enabled"] for section in config["cut_versions"].values()
    ) == 1
    assert "export_cuts" in calls


def test_main_use_cut_decision_copies_file_and_exports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)
    source = tmp_path / "manual.csv"
    source.write_text("node_id\n", encoding="utf-8")
    copied: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        cli.shutil,
        "copy2",
        lambda source_path, destination: copied.append(
            (Path(source_path), Path(destination))
        ),
    )

    result = cli.main(["--project-dir", str(tmp_path), "--use-cut-decision", str(source)])

    assert result == 0
    assert copied == [(source, tmp_path / "output" / "cut_decision.csv")]
    assert "export_cuts" in calls


def test_main_use_existing_project_cut_decision_skips_same_file_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cli = load_cli_module()
    calls: list[object] = []
    patch_cli_dependencies(monkeypatch, cli, calls)
    source = tmp_path / "output" / "cut_decision.csv"
    source.parent.mkdir()
    source.write_text("node_id\n", encoding="utf-8")
    monkeypatch.setattr(
        cli.shutil,
        "copy2",
        lambda *_args: pytest.fail("same file must not be copied"),
    )

    result = cli.main(["--project-dir", str(tmp_path), "--use-cut-decision", str(source)])

    assert result == 0
    assert "export_cuts" in calls


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
    assert "--analyze-nodes" in message
    assert "--export-cuts" in message
    assert "--build-llm-package" in message
    assert "--apply-llm-decision" in message
    assert "--export-with-hook" in message
    assert "GUI" in message
    assert "python app.py" in message
    assert calls == []
