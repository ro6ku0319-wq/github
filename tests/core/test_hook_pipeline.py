from __future__ import annotations

from pathlib import Path

import pytest

from src.core.hook_pipeline import HookPipeline


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> None:
        self.commands.append(command)


def test_hook_pipeline_normalizes_hook_and_prepends_existing_body_cuts(
    tmp_path: Path,
) -> None:
    hook = tmp_path / "input" / "hook" / "intro.mp4"
    hook.parent.mkdir(parents=True)
    hook.write_bytes(b"hook")
    output = tmp_path / "output"
    output.mkdir()
    (output / "body_cut_45s.mp4").write_bytes(b"45")
    (output / "body_cut_60s.mp4").write_bytes(b"60")
    runner = FakeRunner()
    logs: list[str] = []

    result = HookPipeline(
        tmp_path,
        {
            "output": {"output_dir": "output"},
            "external_hook": {
                "enabled": True,
                "hook_video_path": "input/hook/intro.mp4",
                "concat_with_body_cut": True,
                "expected_duration_seconds": 2.5,
            },
            "output_video": {
                "width": 2560,
                "height": 1440,
                "fps": 30,
                "pixel_format": "yuv420p",
            },
        },
        log=logs.append,
        runner=runner,
    ).run_all()

    assert [path.name for path in result.outputs] == [
        "final_with_hook_45s.mp4",
        "final_with_hook_60s.mp4",
    ]
    assert len(runner.commands) == 3
    normalize = " ".join(runner.commands[0])
    assert "scale=2560:1440:force_original_aspect_ratio=increase,crop=2560:1440" in normalize
    assert "normalized_hook.mp4" in normalize
    assert "-t 2.5" in normalize
    concat_text = "\n".join(" ".join(command) for command in runner.commands[1:])
    assert "concat=n=2:v=1:a=0[outv]" in concat_text
    assert "-c:v libx264" in concat_text
    assert "-c copy" not in concat_text
    assert "final_with_hook_45s.mp4" in concat_text
    assert "final_with_hook_60s.mp4" in concat_text
    assert "final_with_hook_120s.mp4" not in concat_text
    assert any("Blender Hook 拼接完成" in message for message in logs)


def test_hook_pipeline_rejects_disabled_hook(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="未启用"):
        HookPipeline(tmp_path, {}, runner=FakeRunner()).run_all()
