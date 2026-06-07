import os
import re
from pathlib import Path

import pytest
import yaml

import src.core.config_manager as config_manager
from src.core.config_manager import ConfigManager


def test_load_merges_project_overrides_with_defaults(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "config.yaml").write_text(
        """
project:
  name: demo
base_processing:
  acceleration_factor: 4.0
""".lstrip(),
        encoding="utf-8",
    )

    config = ConfigManager(project_dir).load()

    assert config["project"]["name"] == "demo"
    assert config["base_processing"]["acceleration_factor"] == 4.0
    assert config["base_processing"]["create_full_concat"] is True
    assert config["output_video"]["width"] == 1080


def test_load_returns_defaults_when_project_config_is_missing(tmp_path: Path) -> None:
    manager = ConfigManager(tmp_path / "project")
    defaults = yaml.safe_load(manager.default_path.read_text(encoding="utf-8"))

    assert manager.load() == defaults
    assert manager.load()["base_processing"]["acceleration_factor"] == 5.0


def test_save_and_load_round_trip_unicode_with_nested_custom_config_path(
    tmp_path: Path,
) -> None:
    manager = ConfigManager(tmp_path / "project", config_name="nested/config.yaml")

    manager.save({"project": {"name": "雕刻项目"}, "custom": {"标签": "完成"}})

    config = manager.load()
    assert config["project"]["name"] == "雕刻项目"
    assert config["custom"]["标签"] == "完成"


def test_resolve_path_uses_project_dir_and_preserves_absolute_paths(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(project_dir)
    absolute_input = project_dir / "input" / "video.mp4"

    assert manager.resolve_path("output") == project_dir / "output"
    assert manager.resolve_path(absolute_input) == absolute_input


@pytest.mark.skipif(os.name != "nt", reason="Windows path semantics only")
def test_resolve_path_preserves_windows_style_string_absolute_paths(
    tmp_path: Path,
) -> None:
    manager = ConfigManager(tmp_path / "project")
    absolute_input = str(tmp_path / "input" / "video.mp4")

    assert manager.resolve_path(absolute_input) == Path(absolute_input).resolve()


@pytest.mark.parametrize("yaml_content", ["null\n", "- item\n", "plain scalar\n"])
def test_load_rejects_non_mapping_yaml(
    tmp_path: Path,
    yaml_content: str,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    config_path = project_dir / "config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")

    with pytest.raises(ValueError, match=re.escape(str(config_path))) as exc_info:
        ConfigManager(project_dir).load()

    assert type(exc_info.value) is config_manager.ConfigError
