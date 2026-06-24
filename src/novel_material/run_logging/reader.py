"""按 run_id 严格重读日期目录下的轮转 JSONL 事件。"""

from __future__ import annotations

import json
from pathlib import Path
import re

from pydantic import ValidationError

from novel_material.runtime.contracts import RunEvent


_DATE_DIRECTORY = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class RunLogReadError(RuntimeError):
    """JSONL 日志无法读取或指定行不符合 RunEvent 契约。"""

    def __init__(self, path: Path, line_number: int) -> None:
        self.path = Path(path)
        self.line_number = line_number
        super().__init__(f"运行日志损坏：{self.path}:{line_number}")


def read_run_events(log_dir: Path, run_id: str) -> tuple[RunEvent, ...]:
    """合并指定运行的全部轮转 JSONL，按 event_id 去重并排序。"""
    root = Path(log_dir)
    if not root.exists():
        return ()

    safe_run_id = re.sub(r"[^A-Za-z0-9_-]+", "-", run_id)
    filename_pattern = re.compile(
        rf"_{re.escape(safe_run_id)}(?:\.\d+)?\.jsonl\Z"
    )
    events_by_id: dict[str, RunEvent] = {}
    try:
        date_directories = sorted(
            path
            for path in root.iterdir()
            if path.is_dir() and _DATE_DIRECTORY.fullmatch(path.name)
        )
    except OSError as exc:
        raise RunLogReadError(root, 0) from exc

    for directory in date_directories:
        try:
            paths = sorted(
                path
                for path in directory.glob("*.jsonl")
                if filename_pattern.search(path.name)
            )
        except OSError as exc:
            raise RunLogReadError(directory, 0) from exc
        for path in paths:
            _read_path(path, run_id, events_by_id)

    return tuple(
        sorted(
            events_by_id.values(),
            key=lambda item: (item.occurred_at, item.event_id),
        )
    )


def _read_path(
    path: Path,
    run_id: str,
    events_by_id: dict[str, RunEvent],
) -> None:
    line_number = 0
    try:
        with path.open("r", encoding="utf-8") as source:
            for line_number, line in enumerate(source, start=1):
                try:
                    payload = json.loads(line)
                    item = RunEvent.model_validate(payload)
                except (json.JSONDecodeError, ValidationError, TypeError) as exc:
                    raise RunLogReadError(path, line_number) from exc
                if item.run_id == run_id:
                    events_by_id.setdefault(item.event_id, item)
    except RunLogReadError:
        raise
    except (OSError, UnicodeError) as exc:
        raise RunLogReadError(path, max(line_number, 1)) from exc


__all__ = ["RunLogReadError", "read_run_events"]
