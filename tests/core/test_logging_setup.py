import re
from pathlib import Path

from src.core.logging_setup import ProjectLogger


def test_project_logger_creates_logs_dir_and_timestamped_log_path(
    tmp_path: Path,
) -> None:
    logs_dir = tmp_path / "logs"

    logger = ProjectLogger(logs_dir)

    assert logs_dir.is_dir()
    assert logger.path.parent == logs_dir
    assert re.fullmatch(r"bodycut-\d{8}-\d{6}\.log", logger.path.name)


def test_project_logger_writes_utf8_chinese_message_with_timestamp_and_mirrors_raw_message(
    tmp_path: Path,
) -> None:
    mirrored: list[str] = []
    logger = ProjectLogger(tmp_path / "logs", sink=mirrored.append)
    message = "开始测试：中文日志"

    logger(message)

    assert mirrored == [message]
    text = logger.path.read_bytes().decode("utf-8")
    assert message in text
    assert re.search(
        rf"^\[\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}}\] {re.escape(message)}$",
        text,
        re.MULTILINE,
    )
