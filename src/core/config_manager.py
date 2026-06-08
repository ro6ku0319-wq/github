from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


class ConfigManager:
    def __init__(self, project_dir: Path, config_name: str = "config.yaml") -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config_path = self.project_dir / config_name
        self.default_path = Path(__file__).resolve().parents[2] / "config.yaml"

    def load(self) -> dict[str, Any]:
        defaults = self._read_yaml(self.default_path)
        if self.config_path == self.default_path or not self.config_path.exists():
            return defaults
        return _deep_merge(defaults, self._read_yaml(self.config_path))

    def save(self, config: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def resolve_path(self, value: str | Path) -> Path:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (self.project_dir / path).resolve()

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ConfigError(f"Configuration file must contain a mapping: {path}")
        return data
