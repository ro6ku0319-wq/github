import subprocess
from collections.abc import Iterator

import pytest

from src.core.ffmpeg_runner import FFmpegRunner, ToolMissingError


class FakeProcess:
    def __init__(self, output_lines: list[str], return_code: int) -> None:
        self.stdout: Iterator[str] = iter(output_lines)
        self.return_code = return_code
        self.wait_calls = 0

    def wait(self) -> int:
        self.wait_calls += 1
        return self.return_code


def install_fake_popen(
    monkeypatch: pytest.MonkeyPatch,
    process: FakeProcess,
) -> list[tuple[list[str], dict[str, object]]]:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def popen(command: list[str], **kwargs: object) -> FakeProcess:
        calls.append((command, kwargs))
        return process

    monkeypatch.setattr("src.core.ffmpeg_runner.subprocess.Popen", popen)
    return calls


def test_validate_tools_checks_ffmpeg_and_ffprobe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checked_tools: list[str] = []

    def which(name: str) -> str:
        checked_tools.append(name)
        return f"C:/tools/{name}.exe"

    monkeypatch.setattr("src.core.ffmpeg_runner.shutil.which", which)

    FFmpegRunner.validate_tools()

    assert checked_tools == ["ffmpeg", "ffprobe"]


@pytest.mark.parametrize(
    ("missing_tool", "expected_checked_tools"),
    [
        ("ffmpeg", ["ffmpeg"]),
        ("ffprobe", ["ffmpeg", "ffprobe"]),
    ],
)
def test_validate_tools_reports_missing_tool_and_path_in_simplified_chinese(
    monkeypatch: pytest.MonkeyPatch,
    missing_tool: str,
    expected_checked_tools: list[str],
) -> None:
    checked_tools: list[str] = []

    def which(name: str) -> str | None:
        checked_tools.append(name)
        return None if name == missing_tool else f"C:/tools/{name}.exe"

    monkeypatch.setattr("src.core.ffmpeg_runner.shutil.which", which)

    with pytest.raises(
        ToolMissingError,
        match=rf"未找到 {missing_tool}。请安装 FFmpeg 并加入 PATH。",
    ):
        FFmpegRunner.validate_tools()

    assert checked_tools == expected_checked_tools


def test_run_logs_command_forwards_stripped_output_and_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs: list[str] = []
    command = ["ffmpeg", "-i", "input clip.mp4", "-an", "output.mp4"]
    process = FakeProcess(["  frame=1  \n", "progress=done\r\n"], return_code=0)
    calls = install_fake_popen(monkeypatch, process)

    FFmpegRunner(log=logs.append).run(command)

    assert logs == [
        "FFmpeg: " + subprocess.list2cmdline(command),
        "frame=1",
        "progress=done",
    ]
    assert calls == [
        (
            command,
            {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
            },
        )
    ]
    assert process.wait_calls == 1


def test_run_raises_clear_error_for_nonzero_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logs: list[str] = []
    command = ["ffmpeg", "-version"]
    process = FakeProcess(["  conversion failed  \n"], return_code=7)
    install_fake_popen(monkeypatch, process)

    with pytest.raises(RuntimeError, match=r"FFmpeg 执行失败，退出码: 7"):
        FFmpegRunner(log=logs.append).run(command)

    assert logs == [
        "FFmpeg: " + subprocess.list2cmdline(command),
        "conversion failed",
    ]
    assert process.wait_calls == 1
