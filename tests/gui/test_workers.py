from __future__ import annotations

from src.gui.workers import TaskWorker


def test_task_worker_reports_elapsed_time_on_success() -> None:
    messages: list[str] = []
    worker = TaskWorker(lambda _signals: None, "测试任务")
    worker.signals.succeeded.connect(messages.append)

    worker.run()

    assert messages
    assert "测试任务 完成" in messages[0]
    assert "耗时" in messages[0]


def test_task_worker_reports_elapsed_time_on_failure() -> None:
    messages: list[str] = []

    def fail(_signals) -> None:
        raise RuntimeError("boom")

    worker = TaskWorker(fail, "测试任务")
    worker.signals.failed.connect(messages.append)

    worker.run()

    assert messages
    assert "测试任务 失败: boom" in messages[0]
    assert "耗时" in messages[0]
