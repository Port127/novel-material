"""按运行隔离并按大小轮转的 JSONL sink。"""

from __future__ import annotations

from pathlib import Path
import re

from novel_material.runtime.contracts import RunEvent
from novel_material.runtime.dispatcher import SinkCriticality

from .serializer import serialize_event


class JsonlSink:
    name = "jsonl"
    criticality = SinkCriticality.REQUIRED

    def __init__(
        self,
        log_dir: Path,
        *,
        command: str,
        run_id: str,
        max_bytes: int,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.command = re.sub(r"[^A-Za-z0-9_-]+", "-", command).strip("-") or "run"
        self.run_id = re.sub(r"[^A-Za-z0-9_-]+", "-", run_id)
        self.max_bytes = max(1, max_bytes)
        self._part = 0
        self._path: Path | None = None

    def emit(self, event: RunEvent) -> None:
        encoded = (serialize_event(event) + "\n").encode("utf-8")
        path = self._current_path(event)
        if path.exists() and path.stat().st_size > 0 and path.stat().st_size + len(encoded) > self.max_bytes:
            self._part += 1
            self._path = None
            path = self._current_path(event)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as output:
            output.write(encoded)

    def _current_path(self, event: RunEvent) -> Path:
        if self._path is None:
            directory = self.log_dir / event.occurred_at.date().isoformat()
            suffix = "" if self._part == 0 else f".{self._part}"
            self._path = directory / f"{self.command}_{self.run_id}{suffix}.jsonl"
        return self._path

    def close(self) -> None:
        """兼容具有生命周期的 sink；当前实现每次 emit 都关闭文件。"""


__all__ = ["JsonlSink"]
