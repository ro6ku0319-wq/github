from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path


class ProjectLogger:
    def __init__(self, logs_dir: Path, sink: Callable[[str], None] | None = None) -> None:
        logs_dir = Path(logs_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = logs_dir / f"bodycut-{stamp}.log"
        self.sink = sink

    def __call__(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"[{timestamp}] {message}\n")
        if self.sink is not None:
            self.sink(message)
