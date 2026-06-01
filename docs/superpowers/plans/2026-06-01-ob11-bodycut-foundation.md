# OB11 Body Cut Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable Windows desktop slice: configuration, multi-video ordering, `ffprobe` inspection, global timeline mapping, FFmpeg concatenation, 8x acceleration, a Chinese PySide6 GUI, and a shared debugging CLI.

**Architecture:** Keep video-processing behavior in `src/core/` and make both GUI and CLI call the same `FoundationPipeline`. Use FFmpeg and `ffprobe` subprocesses for media work, PySide6 workers for non-blocking GUI execution, and structured reports for later node-analysis plans.

**Tech Stack:** Python 3.10+, PySide6, PyYAML, FFmpeg, ffprobe, pytest

---

## Scope Boundary

This is plan 1 of 4. It must produce working, testable software on its own.

Later plans extend the runnable foundation without rewriting it:

1. `2026-06-01-ob11-bodycut-node-analysis.md`: sampling, caches, visual features, candidate recall, fine boundaries, contact sheets, and activity curves.
2. `2026-06-01-ob11-bodycut-review-and-exports.md`: editable `cut_decision.csv`, 45/60/120-second cuts, previews, scoring, and DaVinci markers.
3. `2026-06-01-ob11-bodycut-llm-hook-hardening.md`: LLM evidence package, LLM decision execution, Blender hook concatenation, full GUI pages, documentation, and two-hour acceptance testing.

The current workspace is not a Git repository. Each commit step below is an
intended checkpoint. Run it only after the user authorizes `git init`; otherwise
record the checkpoint as skipped and continue without pretending a commit
exists.

## File Map

Create these files in this plan:

```text
README.md
requirements.txt
config.yaml
app.py
make_timelapse.py
src/__init__.py
src/core/__init__.py
src/core/config_manager.py
src/core/file_collector.py
src/core/video_probe.py
src/core/timeline_mapper.py
src/core/ffmpeg_runner.py
src/core/base_processing.py
src/core/report_writer.py
src/core/logging_setup.py
src/core/pipeline.py
src/gui/__init__.py
src/gui/workers.py
src/gui/log_panel.py
src/gui/input_panel.py
src/gui/processing_panel.py
src/gui/main_window.py
tests/core/test_config_manager.py
tests/core/test_file_collector.py
tests/core/test_video_probe.py
tests/core/test_timeline_mapper.py
tests/core/test_base_processing.py
tests/core/test_logging_setup.py
tests/core/test_pipeline.py
tests/gui/test_main_window.py
tests/test_cli.py
tests/test_project_layout.py
```

File responsibilities:

- `config_manager.py`: load defaults, merge project YAML, resolve project-relative paths, and save configuration.
- `file_collector.py`: discover supported videos, apply `order.txt`, natural-sort names, and emit ordering warnings.
- `video_probe.py`: call `ffprobe` and normalize metadata into typed records.
- `timeline_mapper.py`: build global-to-source time ranges.
- `ffmpeg_runner.py`: validate FFmpeg tools, run subprocesses, and forward command output to log callbacks.
- `base_processing.py`: create `full_concat.mp4` and `accelerated_base.mp4`.
- `report_writer.py`: serialize ordering, metadata, timeline, warnings, and output paths.
- `logging_setup.py`: append timestamped logs to `logs/` and optionally mirror them into GUI or CLI sinks.
- `pipeline.py`: orchestrate the runnable foundation and expose progress callbacks.
- `workers.py`: execute pipeline callables off the GUI thread.
- `input_panel.py`: scan, display, reorder, and save input ordering.
- `processing_panel.py`: trigger concat, acceleration, and one-click foundation processing.
- `main_window.py`: assemble the left workflow navigation, active panel, bottom progress bar, and log panel.

### Task 1: Scaffold Configuration And Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `src/__init__.py`
- Create: `src/core/__init__.py`
- Create: `src/core/config_manager.py`
- Test: `tests/core/test_config_manager.py`

- [ ] **Step 1: Write the failing configuration tests**

```python
from pathlib import Path

from src.core.config_manager import ConfigManager


def test_load_merges_project_yaml_with_defaults(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "project:\n  name: demo\nbase_processing:\n  acceleration_factor: 4.0\n",
        encoding="utf-8",
    )

    config = ConfigManager(tmp_path).load()

    assert config["project"]["name"] == "demo"
    assert config["base_processing"]["acceleration_factor"] == 4.0
    assert config["output_video"]["width"] == 1080


def test_resolve_path_keeps_relative_paths_inside_project(tmp_path: Path) -> None:
    manager = ConfigManager(tmp_path)

    assert manager.resolve_path("output") == tmp_path / "output"
    assert manager.resolve_path(tmp_path / "input") == tmp_path / "input"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/core/test_config_manager.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'src'` or
`ModuleNotFoundError: No module named 'src.core.config_manager'`.

- [ ] **Step 3: Create dependency manifest**

```text
PySide6>=6.7,<7
PyYAML>=6.0,<7
opencv-python>=4.10,<5
numpy>=2.0,<3
tqdm>=4.66,<5
matplotlib>=3.9,<4
pytest>=8.2,<9
```

- [ ] **Step 4: Create the complete default `config.yaml`**

```yaml
project:
  name: "OB11_ZBrush_BodyCut"
  platform: "xiaohongshu"

input:
  input_dir: "input"
  order_file: "input/order.txt"

output:
  output_dir: "output"
  logs_dir: "logs"

external_hook:
  enabled: false
  hook_video_path: ""
  expected_duration_seconds: 2.0
  generated_by: "Blender"
  concat_with_body_cut: true

base_processing:
  create_full_concat: true
  create_accelerated_base: true
  acceleration_factor: 8.0
  preserve_audio: false

output_video:
  width: 1080
  height: 1920
  fps: 30
  codec: "h264"
  pixel_format: "yuv420p"
  crop_mode: "center"
  custom_crop_x: 0
  custom_crop_y: 0
  custom_crop_w: 1080
  custom_crop_h: 1920

fine_cut:
  enabled: true
  allow_subsecond_cuts: true
  timecode_precision: "frame"
  coarse_sample_interval_seconds: 0.4
  fine_sample_every_n_frames: 2
  boundary_search_window_seconds: 1.0
  completion_hold_frames: 3
  min_node_duration_seconds: 0.25

body_cut_rules:
  no_intro_hook_in_body_cut: true
  start_with_sculpting_process: true
  first_20s_min_change_nodes: 3
  require_visual_highlight: true
  allow_final_display_at_end: true
  final_display_at_end_seconds: 3

cut_versions:
  body_45s:
    enabled: true
    target_duration_seconds: 45
  body_60s:
    enabled: true
    target_duration_seconds: 60
  body_120s:
    enabled: true
    target_duration_seconds: 120

operation_priority:
  final_display: 6
  front_hair_strand_pull: 9
  hair_detail: 9
  face_features: 9
  accessory_detail: 8
  rotate_inspect: 3
  zoom_pan_view: 1
  back_hair: 3
  hair_tail: 2
  ui_tool_switch: 1
  static_low_value: 0
  undo_redo_candidate: 0
  blank_or_black: 0

llm_package:
  enabled: true
  overview_sample_interval_seconds: 2
  high_detail_rear_ratio: 0.4
  max_contact_sheet_items_per_page: 60

gui:
  theme: "system"
  remember_last_project: true
  open_output_after_export: true
```

- [ ] **Step 5: Implement `ConfigManager`**

```python
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


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
        self.project_dir.mkdir(parents=True, exist_ok=True)
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
        return data if isinstance(data, dict) else {}
```

- [ ] **Step 6: Run configuration tests**

Run: `python -m pytest tests/core/test_config_manager.py -v`

Expected: PASS.

- [ ] **Step 7: Record checkpoint**

If Git is initialized:

```bash
git add requirements.txt config.yaml src tests/core/test_config_manager.py
git commit -m "feat: add project configuration foundation"
```

### Task 2: Collect And Order Input Videos

**Files:**
- Create: `src/core/file_collector.py`
- Test: `tests/core/test_file_collector.py`

- [ ] **Step 1: Write failing collector tests**

```python
from pathlib import Path

import pytest

from src.core.file_collector import InputDirectoryEmptyError, collect_videos, write_order_file


def _touch(path: Path, timestamp: float) -> None:
    path.write_bytes(b"video")
    path.touch()
    path.chmod(0o644)
    import os

    os.utime(path, (timestamp, timestamp))


def test_order_file_wins_and_extra_input_produces_warning(tmp_path: Path) -> None:
    _touch(tmp_path / "part10.mp4", 30)
    _touch(tmp_path / "part2.mp4", 20)
    _touch(tmp_path / "extra.mov", 10)
    (tmp_path / "order.txt").write_text("part10.mp4\npart2.mp4\n", encoding="utf-8")

    result = collect_videos(tmp_path, tmp_path / "order.txt")

    assert [item.path.name for item in result.files] == ["part10.mp4", "part2.mp4"]
    assert "order_file_omits_input: extra.mov" in result.warnings


def test_natural_sort_is_used_without_order_file(tmp_path: Path) -> None:
    _touch(tmp_path / "part10.mp4", 20)
    _touch(tmp_path / "part2.mp4", 10)

    result = collect_videos(tmp_path, tmp_path / "order.txt")

    assert [item.path.name for item in result.files] == ["part2.mp4", "part10.mp4"]


def test_empty_input_directory_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(InputDirectoryEmptyError):
        collect_videos(tmp_path, tmp_path / "order.txt")


def test_write_order_file_saves_one_filename_per_line(tmp_path: Path) -> None:
    order_file = tmp_path / "order.txt"

    write_order_file(order_file, ["part2.mp4", "part10.mp4"])

    assert order_file.read_text(encoding="utf-8") == "part2.mp4\npart10.mp4\n"
```

- [ ] **Step 2: Run collector tests to verify failure**

Run: `python -m pytest tests/core/test_file_collector.py -v`

Expected: FAIL because `src.core.file_collector` does not exist.

- [ ] **Step 3: Implement collector rules**

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv"}


class InputDirectoryEmptyError(ValueError):
    pass


@dataclass(frozen=True)
class InputVideo:
    path: Path
    modified_time: float


@dataclass(frozen=True)
class CollectionResult:
    files: list[InputVideo]
    natural_order: list[str]
    modified_time_order: list[str]
    warnings: list[str]


def _natural_key(path: Path) -> list[str | int]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def collect_videos(input_dir: Path, order_file: Path) -> CollectionResult:
    discovered = [
        InputVideo(path=path.resolve(), modified_time=path.stat().st_mtime)
        for path in Path(input_dir).iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    if not discovered:
        raise InputDirectoryEmptyError(f"输入目录没有可读取的视频: {input_dir}")

    by_name = {item.path.name: item for item in discovered}
    natural = sorted(discovered, key=lambda item: _natural_key(item.path))
    modified = sorted(discovered, key=lambda item: item.modified_time)
    warnings: list[str] = []

    if [item.path.name for item in natural] != [item.path.name for item in modified]:
        warnings.append("filename_and_mtime_order_conflict")

    if Path(order_file).exists():
        requested = [
            line.strip()
            for line in Path(order_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        missing = [name for name in requested if name not in by_name]
        if missing:
            raise FileNotFoundError(f"order.txt 引用不存在的视频: {', '.join(missing)}")
        omitted = sorted(set(by_name) - set(requested))
        warnings.extend(f"order_file_omits_input: {name}" for name in omitted)
        selected = [by_name[name] for name in requested]
    else:
        selected = natural

    return CollectionResult(
        files=selected,
        natural_order=[item.path.name for item in natural],
        modified_time_order=[item.path.name for item in modified],
        warnings=warnings,
    )


def write_order_file(order_file: Path, filenames: list[str]) -> None:
    order_file.parent.mkdir(parents=True, exist_ok=True)
    order_file.write_text("".join(f"{name}\n" for name in filenames), encoding="utf-8")
```

- [ ] **Step 4: Run collector tests**

Run: `python -m pytest tests/core/test_file_collector.py -v`

Expected: PASS.

- [ ] **Step 5: Record checkpoint**

If Git is initialized:

```bash
git add src/core/file_collector.py tests/core/test_file_collector.py
git commit -m "feat: collect and order zbrush video inputs"
```

### Task 3: Probe Videos And Build The Global Timeline

**Files:**
- Create: `src/core/video_probe.py`
- Create: `src/core/timeline_mapper.py`
- Test: `tests/core/test_video_probe.py`
- Test: `tests/core/test_timeline_mapper.py`

- [ ] **Step 1: Write failing `ffprobe` normalization test**

```python
import json
from pathlib import Path
from subprocess import CompletedProcess

from src.core.video_probe import probe_video


def test_probe_video_normalizes_ffprobe_json(monkeypatch, tmp_path: Path) -> None:
    video = tmp_path / "part1.mp4"
    video.write_bytes(b"video")
    payload = {
        "format": {"duration": "42.5"},
        "streams": [
            {"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1", "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    monkeypatch.setattr(
        "src.core.video_probe.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args[0], 0, json.dumps(payload), ""),
    )

    metadata = probe_video(video)

    assert metadata.duration_seconds == 42.5
    assert metadata.resolution == "1920x1080"
    assert metadata.fps == 30.0
    assert metadata.codec == "h264"
    assert metadata.has_audio is True
```

- [ ] **Step 2: Write failing timeline test**

```python
from pathlib import Path

from src.core.timeline_mapper import build_timeline
from src.core.video_probe import VideoMetadata


def test_build_timeline_maps_global_and_source_ranges() -> None:
    items = [
        VideoMetadata(Path("part1.mp4"), 42.0, 1920, 1080, 30.0, "h264", False, 1.0),
        VideoMetadata(Path("part2.mp4"), 36.0, 1920, 1080, 30.0, "h264", False, 2.0),
    ]

    ranges = build_timeline(items)

    assert ranges[0].global_start == 0.0
    assert ranges[0].global_end == 42.0
    assert ranges[1].global_start == 42.0
    assert ranges[1].global_end == 78.0
```

- [ ] **Step 3: Run tests to verify failure**

Run: `python -m pytest tests/core/test_video_probe.py tests/core/test_timeline_mapper.py -v`

Expected: FAIL because the probe and timeline modules do not exist.

- [ ] **Step 4: Implement metadata probing**

```python
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    duration_seconds: float
    width: int
    height: int
    fps: float
    codec: str
    has_audio: bool
    modified_time: float

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"


def _parse_rate(value: str) -> float:
    numerator, denominator = value.split("/", maxsplit=1)
    return float(numerator) / float(denominator)


def probe_video(path: Path) -> VideoMetadata:
    command = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate",
        "-of", "json", str(path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    streams = payload["streams"]
    video = next(stream for stream in streams if stream.get("codec_type") == "video")
    return VideoMetadata(
        path=Path(path).resolve(),
        duration_seconds=float(payload["format"]["duration"]),
        width=int(video["width"]),
        height=int(video["height"]),
        fps=_parse_rate(video["r_frame_rate"]),
        codec=str(video["codec_name"]),
        has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
        modified_time=Path(path).stat().st_mtime,
    )
```

- [ ] **Step 5: Implement timeline mapping**

```python
from __future__ import annotations

from dataclasses import dataclass

from src.core.video_probe import VideoMetadata


@dataclass(frozen=True)
class TimelineRange:
    source_file: str
    global_start: float
    global_end: float
    source_start: float
    source_end: float


def build_timeline(videos: list[VideoMetadata]) -> list[TimelineRange]:
    cursor = 0.0
    result: list[TimelineRange] = []
    for video in videos:
        result.append(
            TimelineRange(
                source_file=str(video.path),
                global_start=cursor,
                global_end=cursor + video.duration_seconds,
                source_start=0.0,
                source_end=video.duration_seconds,
            )
        )
        cursor += video.duration_seconds
    return result
```

- [ ] **Step 6: Run probe and timeline tests**

Run: `python -m pytest tests/core/test_video_probe.py tests/core/test_timeline_mapper.py -v`

Expected: PASS.

- [ ] **Step 7: Record checkpoint**

If Git is initialized:

```bash
git add src/core/video_probe.py src/core/timeline_mapper.py tests/core
git commit -m "feat: probe videos and map global timeline"
```

### Task 4: Run FFmpeg For Concatenation And Acceleration

**Files:**
- Create: `src/core/ffmpeg_runner.py`
- Create: `src/core/base_processing.py`
- Test: `tests/core/test_base_processing.py`

- [ ] **Step 1: Write failing base-processing command tests**

```python
from pathlib import Path

from src.core.base_processing import BaseProcessor, OutputVideoSettings


class RecordingRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> None:
        self.commands.append(command)


def test_create_full_concat_writes_list_and_normalizes_vertical_output(tmp_path: Path) -> None:
    runner = RecordingRunner()
    processor = BaseProcessor(runner, OutputVideoSettings(1080, 1920, 30, "yuv420p"))
    concat_list = tmp_path / "concat.txt"

    processor.create_full_concat(
        [tmp_path / "part1.mp4", tmp_path / "part2.mov"],
        tmp_path / "full_concat.mp4",
        concat_list,
    )

    assert concat_list.read_text(encoding="utf-8").count("file '") == 2
    assert "-f" in runner.commands[0]
    assert "concat" in runner.commands[0]
    assert "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" in " ".join(runner.commands[0])


def test_create_accelerated_base_uses_setpts(tmp_path: Path) -> None:
    runner = RecordingRunner()
    processor = BaseProcessor(runner, OutputVideoSettings(1080, 1920, 30, "yuv420p"))

    processor.create_accelerated_base(tmp_path / "full_concat.mp4", tmp_path / "accelerated_base.mp4", 8.0)

    assert "setpts=PTS/8.0" in " ".join(runner.commands[0])
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/core/test_base_processing.py -v`

Expected: FAIL because `src.core.base_processing` does not exist.

- [ ] **Step 3: Implement FFmpeg runner**

```python
from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable


class ToolMissingError(RuntimeError):
    pass


class FFmpegRunner:
    def __init__(self, log: Callable[[str], None] | None = None) -> None:
        self.log = log or logging.getLogger(__name__).info

    @staticmethod
    def validate_tools() -> None:
        for name in ("ffmpeg", "ffprobe"):
            if shutil.which(name) is None:
                raise ToolMissingError(f"未找到 {name}。请安装 FFmpeg 并加入 PATH。")

    def run(self, command: list[str]) -> None:
        self.log("FFmpeg: " + subprocess.list2cmdline(command))
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            self.log(line.rstrip())
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"FFmpeg 执行失败，退出码: {return_code}")
```

- [ ] **Step 4: Implement base-processing commands**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class CommandRunner(Protocol):
    def run(self, command: list[str]) -> None:
        pass


@dataclass(frozen=True)
class OutputVideoSettings:
    width: int
    height: int
    fps: int
    pixel_format: str


class BaseProcessor:
    def __init__(self, runner: CommandRunner, settings: OutputVideoSettings) -> None:
        self.runner = runner
        self.settings = settings

    def _vertical_filter(self) -> str:
        width = self.settings.width
        height = self.settings.height
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )

    def create_full_concat(self, videos: list[Path], output: Path, concat_list: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        concat_list.parent.mkdir(parents=True, exist_ok=True)
        concat_list.write_text(
            "".join(f"file '{path.resolve().as_posix()}'\n" for path in videos),
            encoding="utf-8",
        )
        self.runner.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-vf", self._vertical_filter(), "-r", str(self.settings.fps),
            "-c:v", "libx264", "-pix_fmt", self.settings.pixel_format, "-an", str(output),
        ])

    def create_accelerated_base(self, source: Path, output: Path, factor: float) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self.runner.run([
            "ffmpeg", "-y", "-i", str(source), "-vf", f"setpts=PTS/{factor}",
            "-r", str(self.settings.fps), "-c:v", "libx264",
            "-pix_fmt", self.settings.pixel_format, "-an", str(output),
        ])
```

- [ ] **Step 5: Run base-processing tests**

Run: `python -m pytest tests/core/test_base_processing.py -v`

Expected: PASS.

- [ ] **Step 6: Record checkpoint**

If Git is initialized:

```bash
git add src/core/ffmpeg_runner.py src/core/base_processing.py tests/core/test_base_processing.py
git commit -m "feat: add ffmpeg base processing"
```

### Task 5: Orchestrate Foundation Pipeline And Reports

**Files:**
- Create: `src/core/report_writer.py`
- Create: `src/core/logging_setup.py`
- Create: `src/core/pipeline.py`
- Test: `tests/core/test_logging_setup.py`
- Test: `tests/core/test_pipeline.py`

- [ ] **Step 1: Write failing file-logging test**

```python
from src.core.logging_setup import ProjectLogger


def test_project_logger_writes_file_and_mirrors_to_sink(tmp_path) -> None:
    mirrored: list[str] = []
    logger = ProjectLogger(tmp_path / "logs", sink=mirrored.append)

    logger("开始测试")

    assert mirrored == ["开始测试"]
    assert "开始测试" in logger.path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Write failing orchestration test**

```python
from pathlib import Path

from src.core.file_collector import CollectionResult, InputVideo
from src.core.pipeline import FoundationPipeline
from src.core.video_probe import VideoMetadata


class FakeProcessor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def create_full_concat(self, videos, output, concat_list) -> None:
        self.calls.append("concat")

    def create_accelerated_base(self, source, output, factor) -> None:
        self.calls.append("accelerate")


def test_run_all_writes_reports_and_runs_both_media_stages(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    source = input_dir / "part1.mp4"
    source.write_bytes(b"video")
    collection = CollectionResult([InputVideo(source, 1.0)], ["part1.mp4"], ["part1.mp4"], [])
    metadata = VideoMetadata(source, 42.0, 1920, 1080, 30.0, "h264", False, 1.0)
    processor = FakeProcessor()
    pipeline = FoundationPipeline(tmp_path, {}, processor=processor, tool_validator=lambda: None)
    monkeypatch.setattr(pipeline, "collect", lambda: collection)
    monkeypatch.setattr(pipeline, "probe", lambda files: [metadata])

    pipeline.run_all()

    assert processor.calls == ["concat", "accelerate"]
    assert (tmp_path / "output" / "input_order.txt").exists()
    assert (tmp_path / "output" / "edit_report.json").exists()
    assert (tmp_path / "output" / "edit_report.txt").exists()
```

- [ ] **Step 3: Run report, log, and pipeline tests to verify failure**

Run: `python -m pytest tests/core/test_logging_setup.py tests/core/test_pipeline.py -v`

Expected: FAIL because `src.core.logging_setup` and `src.core.pipeline` do not exist.

- [ ] **Step 4: Implement timestamped project logging**

```python
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path


class ProjectLogger:
    def __init__(self, logs_dir: Path, sink: Callable[[str], None] | None = None) -> None:
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = logs_dir / f"bodycut-{stamp}.log"
        self.sink = sink

    def __call__(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{timestamp}] {message}\n")
        if self.sink is not None:
            self.sink(message)
```

- [ ] **Step 5: Implement report writing with Windows-path JSON conversion**

```python
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"无法序列化 JSON 值: {type(value).__name__}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )


def write_input_order(path: Path, collection, timeline) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["最终顺序:"]
    lines.extend(f"- {item.path.name}" for item in collection.files)
    lines.append("自然文件名顺序: " + ", ".join(collection.natural_order))
    lines.append("修改时间顺序: " + ", ".join(collection.modified_time_order))
    lines.append("warning: " + (", ".join(collection.warnings) if collection.warnings else "无"))
    lines.append("全局时间轴:")
    lines.extend(
        f"- {item.source_file}: {item.global_start:.3f}s -> {item.global_end:.3f}s"
        for item in timeline
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def dataclass_list(items) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]


def write_edit_report_text(path: Path, metadata, timeline, warnings: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["OB11 ZBrush Body Cut 基础处理报告", "", "输入视频:"]
    lines.extend(
        f"- {item.path.name}: {item.duration_seconds:.3f}s, {item.resolution}, {item.fps:.3f}fps, {item.codec}"
        for item in metadata
    )
    lines.append("")
    lines.append("全局时间轴:")
    lines.extend(
        f"- {item.source_file}: {item.global_start:.3f}s -> {item.global_end:.3f}s"
        for item in timeline
    )
    lines.append("")
    lines.append("warning: " + (", ".join(warnings) if warnings else "无"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
```

- [ ] **Step 6: Implement `FoundationPipeline`**

```python
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.core.base_processing import BaseProcessor, OutputVideoSettings
from src.core.ffmpeg_runner import FFmpegRunner
from src.core.file_collector import CollectionResult, InputVideo, collect_videos
from src.core.report_writer import dataclass_list, write_edit_report_text, write_input_order, write_json
from src.core.timeline_mapper import build_timeline
from src.core.video_probe import VideoMetadata, probe_video


class FoundationPipeline:
    def __init__(
        self,
        project_dir: Path,
        config: dict,
        log: Callable[[str], None] | None = None,
        progress: Callable[[int, str], None] | None = None,
        processor: BaseProcessor | None = None,
        tool_validator: Callable[[], None] | None = None,
    ) -> None:
        self.project_dir = Path(project_dir).resolve()
        self.config = config
        self.log = log or (lambda message: None)
        self.progress = progress or (lambda value, message: None)
        output_video = config.get("output_video", {})
        settings = OutputVideoSettings(
            int(output_video.get("width", 1080)),
            int(output_video.get("height", 1920)),
            int(output_video.get("fps", 30)),
            str(output_video.get("pixel_format", "yuv420p")),
        )
        self.processor = processor or BaseProcessor(FFmpegRunner(self.log), settings)
        self.tool_validator = tool_validator or FFmpegRunner.validate_tools

    @property
    def output_dir(self) -> Path:
        return self.project_dir / self.config.get("output", {}).get("output_dir", "output")

    def collect(self) -> CollectionResult:
        input_dir = self.project_dir / self.config.get("input", {}).get("input_dir", "input")
        order_file = self.project_dir / self.config.get("input", {}).get("order_file", "input/order.txt")
        return collect_videos(input_dir, order_file)

    def probe(self, files: list[InputVideo]) -> list[VideoMetadata]:
        readable: list[VideoMetadata] = []
        for item in files:
            try:
                readable.append(probe_video(item.path))
            except Exception as error:
                self.log(f"跳过无法读取的视频: {item.path} ({error})")
        if not readable:
            raise RuntimeError("所有输入视频都无法读取，基础处理终止。")
        return readable

    def _update(self, value: int, message: str) -> None:
        self.log(message)
        self.progress(value, message)

    def run_all(self) -> None:
        self.tool_validator()
        self._update(5, "扫描输入素材")
        collection = self.collect()
        self._update(15, "读取视频元数据")
        metadata = self.probe(collection.files)
        timeline = build_timeline(metadata)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        write_input_order(self.output_dir / "input_order.txt", collection, timeline)
        write_json(self.output_dir / "edit_report.json", {
            "videos": dataclass_list(metadata),
            "timeline": dataclass_list(timeline),
            "warnings": collection.warnings,
        })
        write_edit_report_text(
            self.output_dir / "edit_report.txt",
            metadata,
            timeline,
            collection.warnings,
        )
        self._update(30, "生成 full_concat.mp4")
        self.processor.create_full_concat(
            [item.path for item in metadata],
            self.output_dir / "full_concat.mp4",
            self.output_dir / "concat_list.txt",
        )
        self.log(f"输出: {self.output_dir / 'full_concat.mp4'}")
        self._update(70, "生成 accelerated_base.mp4")
        factor = float(self.config.get("base_processing", {}).get("acceleration_factor", 8.0))
        self.processor.create_accelerated_base(
            self.output_dir / "full_concat.mp4",
            self.output_dir / "accelerated_base.mp4",
            factor,
        )
        self.log(f"输出: {self.output_dir / 'accelerated_base.mp4'}")
        self._update(100, "基础处理完成")
```

- [ ] **Step 7: Run report, log, and pipeline tests**

Run: `python -m pytest tests/core/test_logging_setup.py tests/core/test_pipeline.py -v`

Expected: PASS.

- [ ] **Step 8: Record checkpoint**

If Git is initialized:

```bash
git add src/core/report_writer.py src/core/logging_setup.py src/core/pipeline.py tests/core
git commit -m "feat: orchestrate foundation processing pipeline"
```

### Task 6: Add Debugging CLI

**Files:**
- Create: `make_timelapse.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI parser test**

```python
from make_timelapse import build_parser


def test_cli_supports_foundation_commands() -> None:
    parser = build_parser()

    assert parser.parse_args(["--only-full-concat"]).only_full_concat is True
    assert parser.parse_args(["--only-accelerate"]).only_accelerate is True
    assert parser.parse_args(["--run-foundation"]).run_foundation is True
```

- [ ] **Step 2: Run CLI test to verify failure**

Run: `python -m pytest tests/test_cli.py -v`

Expected: FAIL because `make_timelapse.py` does not exist.

- [ ] **Step 3: Implement CLI entrypoint**

```python
from __future__ import annotations

import argparse
from pathlib import Path

from src.core.config_manager import ConfigManager
from src.core.logging_setup import ProjectLogger
from src.core.pipeline import FoundationPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="OB11 ZBrush body cut 调试入口")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--only-full-concat", action="store_true")
    parser.add_argument("--only-accelerate", action="store_true")
    parser.add_argument("--run-foundation", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    manager = ConfigManager(args.project_dir)
    config = manager.load()
    logs_dir = args.project_dir / config.get("output", {}).get("logs_dir", "logs")
    pipeline = FoundationPipeline(args.project_dir, config, log=ProjectLogger(logs_dir, sink=print))
    if args.run_foundation:
        pipeline.run_all()
        return 0
    if args.only_full_concat or args.only_accelerate:
        raise SystemExit("单步 CLI 将在基础流水线拆分提交中连接；当前请使用 --run-foundation。")
    raise SystemExit("请选择 --run-foundation。推荐日常使用 GUI: python app.py")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI test**

Run: `python -m pytest tests/test_cli.py -v`

Expected: PASS.

- [ ] **Step 5: Split pipeline single-stage methods and connect CLI switches**

Move the bodies of the two media operations into callable methods:

```python
def create_full_concat(self, metadata: list[VideoMetadata]) -> None:
    self.processor.create_full_concat(
        [item.path for item in metadata],
        self.output_dir / "full_concat.mp4",
        self.output_dir / "concat_list.txt",
    )


def create_accelerated_base(self) -> None:
    factor = float(self.config.get("base_processing", {}).get("acceleration_factor", 8.0))
    self.processor.create_accelerated_base(
        self.output_dir / "full_concat.mp4",
        self.output_dir / "accelerated_base.mp4",
        factor,
    )
```

Update CLI branching:

```python
if args.only_full_concat:
    pipeline.create_full_concat(pipeline.probe(pipeline.collect().files))
    return 0
if args.only_accelerate:
    pipeline.create_accelerated_base()
    return 0
```

- [ ] **Step 6: Add CLI single-stage tests and run them**

Extend `tests/test_cli.py` with monkeypatched pipeline tests that assert:

```python
assert calls == ["collect", "probe", "concat"]
assert calls == ["accelerate"]
```

Run: `python -m pytest tests/test_cli.py tests/core/test_pipeline.py -v`

Expected: PASS.

- [ ] **Step 7: Record checkpoint**

If Git is initialized:

```bash
git add make_timelapse.py src/core/pipeline.py tests
git commit -m "feat: add shared debugging cli"
```

### Task 7: Add Responsive Chinese PySide6 GUI

**Files:**
- Create: `src/gui/__init__.py`
- Create: `src/gui/workers.py`
- Create: `src/gui/log_panel.py`
- Create: `src/gui/input_panel.py`
- Create: `src/gui/processing_panel.py`
- Create: `src/gui/main_window.py`
- Create: `app.py`
- Test: `tests/gui/test_main_window.py`

- [ ] **Step 1: Write failing offscreen GUI smoke test**

```python
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def test_main_window_contains_navigation_progress_and_log_panel(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow(tmp_path)

    assert window.windowTitle() == "OB11 ZBrush Body Cut"
    assert window.navigation.count() >= 4
    assert window.progress_bar.minimum() == 0
    assert window.progress_bar.maximum() == 100
    assert window.log_panel.toPlainText() == ""
    window.close()
    app.processEvents()
```

- [ ] **Step 2: Run GUI test to verify failure**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/gui/test_main_window.py -v
```

Expected: FAIL because `src.gui.main_window` does not exist.

- [ ] **Step 3: Implement worker signals**

```python
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    log = Signal(str)
    progress = Signal(int, str)
    succeeded = Signal(str)
    failed = Signal(str)


class TaskWorker(QRunnable):
    def __init__(self, task: Callable[[WorkerSignals], None], name: str) -> None:
        super().__init__()
        self.task = task
        self.name = name
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.task(self.signals)
            self.signals.succeeded.emit(f"{self.name} 完成")
        except Exception as error:
            self.signals.failed.emit(f"{self.name} 失败: {error}")
```

- [ ] **Step 4: Implement log and action panels**

```python
# src/gui/log_panel.py
from PySide6.QtWidgets import QPlainTextEdit


class LogPanel(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)

    def append_log(self, message: str) -> None:
        self.appendPlainText(message)
```

```python
# src/gui/input_panel.py
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)


class InputPanel(QWidget):
    scan_requested = Signal()
    save_order_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("素材管理"))
        actions = QHBoxLayout()
        self.scan_button = QPushButton("扫描 input 文件夹")
        self.move_up_button = QPushButton("上移")
        self.move_down_button = QPushButton("下移")
        self.save_order_button = QPushButton("保存 order.txt")
        actions.addWidget(self.scan_button)
        actions.addWidget(self.move_up_button)
        actions.addWidget(self.move_down_button)
        actions.addWidget(self.save_order_button)
        layout.addLayout(actions)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文件名", "路径", "顺序"])
        layout.addWidget(self.table)
        self.scan_button.clicked.connect(self.scan_requested.emit)
        self.save_order_button.clicked.connect(self.save_order_requested.emit)
        self.move_up_button.clicked.connect(lambda: self.move_selected(-1))
        self.move_down_button.clicked.connect(lambda: self.move_selected(1))

    def set_files(self, paths: list[Path]) -> None:
        self.table.setRowCount(len(paths))
        for row, path in enumerate(paths):
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem(str(path)))
            self.table.setItem(row, 2, QTableWidgetItem(str(row + 1)))

    def ordered_names(self) -> list[str]:
        return [self.table.item(row, 0).text() for row in range(self.table.rowCount())]

    def move_selected(self, offset: int) -> None:
        row = self.table.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.table.rowCount():
            return
        values = [
            self.table.item(row, column).text()
            for column in range(self.table.columnCount())
        ]
        target_values = [
            self.table.item(target, column).text()
            for column in range(self.table.columnCount())
        ]
        for column, value in enumerate(target_values):
            self.table.setItem(row, column, QTableWidgetItem(value))
        for column, value in enumerate(values):
            self.table.setItem(target, column, QTableWidgetItem(value))
        for current_row in range(self.table.rowCount()):
            self.table.setItem(current_row, 2, QTableWidgetItem(str(current_row + 1)))
        self.table.selectRow(target)
```

```python
# src/gui/processing_panel.py
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class ProcessingPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("基础处理"))
        self.run_foundation = QPushButton("一键执行基础流程")
        layout.addWidget(self.run_foundation)
```

- [ ] **Step 5: Implement main window and app entrypoint**

```python
# src/gui/main_window.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QListWidget, QMainWindow, QProgressBar, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from src.core.config_manager import ConfigManager
from src.core.file_collector import collect_videos, write_order_file
from src.gui.input_panel import InputPanel
from src.gui.log_panel import LogPanel
from src.gui.processing_panel import ProcessingPanel


class MainWindow(QMainWindow):
    def __init__(self, project_dir: Path) -> None:
        super().__init__()
        self.project_dir = Path(project_dir)
        self.setWindowTitle("OB11 ZBrush Body Cut")
        root = QWidget()
        root_layout = QVBoxLayout(root)
        splitter = QSplitter()
        self.navigation = QListWidget()
        self.navigation.addItems(["项目设置", "素材管理", "基础处理", "日志"])
        self.pages = QStackedWidget()
        self.pages.addWidget(QWidget())
        self.input_panel = InputPanel()
        self.pages.addWidget(self.input_panel)
        self.processing_panel = ProcessingPanel()
        self.pages.addWidget(self.processing_panel)
        self.pages.addWidget(QWidget())
        splitter.addWidget(self.navigation)
        splitter.addWidget(self.pages)
        self.progress_bar = QProgressBar()
        self.log_panel = LogPanel()
        self.active_workers = set()
        root_layout.addWidget(splitter)
        root_layout.addWidget(self.progress_bar)
        root_layout.addWidget(self.log_panel)
        self.setCentralWidget(root)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.input_panel.scan_requested.connect(self._scan_inputs)
        self.input_panel.save_order_requested.connect(self._save_input_order)

    def _scan_inputs(self) -> None:
        config = ConfigManager(self.project_dir).load()
        input_dir = self.project_dir / config.get("input", {}).get("input_dir", "input")
        order_file = self.project_dir / config.get("input", {}).get("order_file", "input/order.txt")
        result = collect_videos(input_dir, order_file)
        self.input_panel.set_files([item.path for item in result.files])
        for warning in result.warnings:
            self.log_panel.append_log("warning: " + warning)

    def _save_input_order(self) -> None:
        config = ConfigManager(self.project_dir).load()
        order_file = self.project_dir / config.get("input", {}).get("order_file", "input/order.txt")
        write_order_file(order_file, self.input_panel.ordered_names())
        self.log_panel.append_log(f"已保存素材顺序: {order_file}")
```

```python
# app.py
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(Path.cwd())
    window.resize(1200, 800)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run GUI smoke test**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/gui/test_main_window.py -v
```

Expected: PASS.

- [ ] **Step 7: Connect GUI button to a background pipeline worker**

Add to `MainWindow`:

```python
from PySide6.QtCore import QThreadPool

from src.core.config_manager import ConfigManager
from src.core.logging_setup import ProjectLogger
from src.core.pipeline import FoundationPipeline
from src.gui.workers import TaskWorker


def _run_foundation(self) -> None:
    def task(signals) -> None:
        config = ConfigManager(self.project_dir).load()
        logs_dir = self.project_dir / config.get("output", {}).get("logs_dir", "logs")
        pipeline = FoundationPipeline(
            self.project_dir,
            config,
            log=ProjectLogger(logs_dir, sink=signals.log.emit),
            progress=signals.progress.emit,
        )
        pipeline.run_all()

    worker = TaskWorker(task, "基础处理")
    worker.signals.log.connect(self.log_panel.append_log)
    worker.signals.progress.connect(self._set_progress)
    worker.signals.succeeded.connect(lambda message: self._finish_worker(worker, message))
    worker.signals.failed.connect(lambda message: self._finish_worker(worker, message))
    self.active_workers.add(worker)
    self.thread_pool.start(worker)


def _set_progress(self, value: int, message: str) -> None:
    self.progress_bar.setValue(value)
    self.log_panel.append_log(message)


def _finish_worker(self, worker: TaskWorker, message: str) -> None:
    self.log_panel.append_log(message)
    self.active_workers.discard(worker)
```

Initialize and connect:

```python
self.thread_pool = QThreadPool.globalInstance()
self.processing_panel.run_foundation.clicked.connect(self._run_foundation)
```

- [ ] **Step 8: Extend GUI test to verify button wiring**

Add:

```python
assert window.processing_panel.run_foundation.text() == "一键执行基础流程"
assert window.thread_pool.maxThreadCount() >= 1
window.input_panel.set_files([tmp_path / "part1.mp4", tmp_path / "part2.mp4"])
window.input_panel.table.selectRow(1)
window.input_panel.move_selected(-1)
assert window.input_panel.ordered_names() == ["part2.mp4", "part1.mp4"]
```

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest tests/gui/test_main_window.py -v
```

Expected: PASS.

- [ ] **Step 9: Record checkpoint**

If Git is initialized:

```bash
git add app.py src/gui tests/gui
git commit -m "feat: add responsive chinese desktop gui"
```

### Task 8: Document And Verify The Runnable Foundation

**Files:**
- Create: `README.md`
- Test: `tests/test_project_layout.py`

- [ ] **Step 1: Write failing project-layout test**

```python
from pathlib import Path


def test_foundation_entrypoints_and_docs_exist() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "app.py").exists()
    assert (root / "make_timelapse.py").exists()
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "python app.py" in readme
    assert "full_concat.mp4" in readme
    assert "accelerated_base.mp4" in readme
    assert "Blender Hook" in readme
```

- [ ] **Step 2: Run layout test to verify failure**

Run: `python -m pytest tests/test_project_layout.py -v`

Expected: FAIL because `README.md` does not exist.

- [ ] **Step 3: Write Chinese README foundation guide**

Create `README.md` with these concrete sections:

```markdown
# OB11 ZBrush Body Cut

## 当前能力
本工具用于整理 ZBrush 自带缩时录制产生的多段视频。首个可运行切片支持素材排序、探测、拼接、8 倍加速和异步 GUI 日志。

## 边界
本工具只处理雕刻过程 body cut。Blender Hook 由用户制作；标题、BGM、字幕、片尾和最终微调在 DaVinci Resolve 中完成。

## Windows 安装
1. 安装 Python 3.10 或更高版本。
2. 安装 FFmpeg，并确认 `ffmpeg -version` 和 `ffprobe -version` 可运行。
3. 执行 `python -m pip install -r requirements.txt`。

## GUI 启动
执行 `python app.py`。

## 素材放置与排序
将 `.mp4`、`.mov` 或 `.mkv` 文件放入 `input/`。如需固定顺序，在 `input/order.txt` 中每行填写一个文件名。

## 基础输出
- `output/full_concat.mp4`：按顺序拼接的归档视频。
- `output/accelerated_base.mp4`：在拼接结果上再次加速的分析基础视频。
- `output/input_order.txt`：最终顺序、排序对比、warning 和全局时间轴。
- `output/edit_report.json`：机器可读元数据和时间轴。
- `output/edit_report.txt`：便于人工阅读的视频信息、时间轴和 warning。
- `logs/bodycut-*.log`：FFmpeg 命令、处理步骤、warning 和错误。

## 调试 CLI
推荐使用 GUI。高级调试可执行：

```powershell
python make_timelapse.py --run-foundation
python make_timelapse.py --only-full-concat
python make_timelapse.py --only-accelerate
```

## 后续切片
后续版本继续加入节点分析、人工审核、45/60/120 秒 body cut、LLM 证据包和 Blender Hook 自动拼接。
```

- [ ] **Step 4: Create runtime directories**

Create:

```text
input/
input/hook/
output/
logs/
```

Add empty `.gitkeep` files only when Git is initialized.

- [ ] **Step 5: Run full unit suite**

Run:

```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 6: Check external tools**

Run:

```powershell
ffmpeg -version
ffprobe -version
```

Expected: both commands print installed versions and exit with code `0`.

- [ ] **Step 7: Run GUI smoke launch**

Run:

```powershell
python app.py
```

Expected: a Chinese desktop window opens with left navigation, an input panel,
a base-processing panel, a bottom progress bar, and a real-time log panel.

- [ ] **Step 8: Run real-footage foundation acceptance**

Place a user-provided ZBrush excerpt in `input/`, then run the GUI one-click
foundation process.

Expected files:

```text
output/input_order.txt
output/edit_report.json
output/edit_report.txt
output/full_concat.mp4
output/accelerated_base.mp4
logs/bodycut-*.log
```

Expected behavior:

- The GUI remains responsive.
- Progress reaches `100`.
- Logs show FFmpeg commands and output paths in the GUI and `logs/bodycut-*.log`.
- Original source footage remains unchanged.

- [ ] **Step 9: Record checkpoint**

If Git is initialized:

```bash
git add README.md input output logs tests
git commit -m "docs: document runnable bodycut foundation"
```

## Plan Self-Review

- Spec coverage for this slice: configuration, editable input ordering, `ffprobe`,
  timeline mapping, `full_concat.mp4`, `accelerated_base.mp4`, shared CLI, GUI,
  async execution, Chinese text, file-backed logs, and real-footage validation are assigned
  to explicit tasks.
- Deferred work is explicitly partitioned into the three named follow-up plans.
- All paths, commands, test names, and callable interfaces used by later tasks
  are defined earlier in this plan.
- No source footage is overwritten.
- The GUI and CLI reuse `FoundationPipeline`; video processing does not leak
  into GUI widgets.
