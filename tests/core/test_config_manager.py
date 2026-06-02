from pathlib import Path

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
    assert config["output_video"]["width"] == 1080


def test_resolve_path_uses_project_dir_and_preserves_absolute_paths(
    tmp_path: Path,
) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    manager = ConfigManager(project_dir)
    absolute_input = project_dir / "input" / "video.mp4"

    assert manager.resolve_path("output") == project_dir / "output"
    assert manager.resolve_path(absolute_input) == absolute_input
