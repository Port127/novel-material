"""唯一 Rich Progress 工厂。"""

from __future__ import annotations

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


def create_progress(*, console) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


def finish_task(progress: Progress, task_id: int, *, status: str) -> None:
    symbols = {"success": "✓", "degraded": "△", "failed": "✗"}
    symbol = symbols.get(status, "✗")
    task = next(task for task in progress.tasks if task.id == task_id)
    update = {"description": f"{symbol} {task.description}"}
    if task.total is None:
        update.update(total=1, completed=1)
    progress.update(task_id, **update)
    progress.stop_task(task_id)


__all__ = ["create_progress", "finish_task"]
