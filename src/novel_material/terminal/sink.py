"""将中立运行事件渲染为终端进度。"""

from __future__ import annotations

from rich.progress import Progress

from novel_material.runtime.contracts import RunEvent, RunStatus
from novel_material.runtime.dispatcher import SinkCriticality

from .modes import TerminalMode
from .progress import create_progress, finish_task
from .reporter import TerminalReporter


_STAGE_LABELS = {
    "evaluation": "前置导航",
    "analyze": "章级分析",
    "outline": "大纲生成",
    "worldbuilding": "世界观提取",
    "characters": "人物提取",
    "tags": "标签生成",
    "insights": "深度分析",
    "refine": "数据精调",
    "profile": "作品画像",
    "audit": "产物审计",
    "sync": "数据库同步",
}


class TerminalEventSink:
    """消费 RunEvent，并在 TTY/Plain 模式下展示阶段级进度。"""

    name = "terminal"
    criticality = SinkCriticality.BEST_EFFORT

    def __init__(self, reporter: TerminalReporter) -> None:
        self._reporter = reporter
        self._expected = 0
        self._completed = 0
        self._current_stage = ""
        self._progress: Progress | None = None
        self._task_id: int | None = None

    def emit(self, event: RunEvent) -> None:
        if self._reporter.mode in {TerminalMode.JSON, TerminalMode.QUIET}:
            return
        if event.event_name == "RunStarted":
            self._start(event)
        elif event.event_name == "StageStarted":
            self._stage_started(event)
        elif event.event_name == "StageCompleted":
            self._stage_completed(event)
        elif event.event_name == "RunCompleted":
            self._stop()

    def _start(self, event: RunEvent) -> None:
        self._expected = int(event.attributes.get("expected_stages") or 0)
        self._completed = 0
        if self._reporter.mode is TerminalMode.TTY:
            self._progress = create_progress(console=self._reporter.stderr)
            self._progress.start()

    def _stage_started(self, event: RunEvent) -> None:
        stage_name = str(event.attributes.get("stage_name") or event.operation)
        self._current_stage = stage_name
        description = self._description(stage_name)
        if self._reporter.mode is TerminalMode.PLAIN:
            self._reporter.progress(
                description=description,
                completed=self._completed,
                total=self._expected,
            )
            return
        if self._progress is None:
            return
        if self._task_id is None:
            self._task_id = self._progress.add_task(
                description,
                total=self._expected or None,
                completed=self._completed,
            )
        else:
            self._progress.update(
                self._task_id,
                description=description,
                total=self._expected or None,
                completed=self._completed,
            )

    def _stage_completed(self, event: RunEvent) -> None:
        stage_name = str(
            event.attributes.get("stage_name")
            or self._current_stage
            or event.operation
        )
        description = self._description(stage_name)
        self._completed += 1
        if self._reporter.mode is TerminalMode.PLAIN:
            self._reporter.progress(
                description=description,
                completed=self._completed,
                total=self._expected,
            )
            return
        if self._progress is None or self._task_id is None:
            return
        self._progress.update(
            self._task_id,
            description=description,
            total=self._expected or None,
            completed=self._completed,
        )
        if event.status not in {RunStatus.SUCCESS, None}:
            finish_task(
                self._progress,
                self._task_id,
                status=event.status.value,
            )

    def _stop(self) -> None:
        if self._progress is None:
            return
        if self._task_id is not None:
            self._progress.update(
                self._task_id,
                completed=self._expected or self._completed,
            )
            self._progress.stop_task(self._task_id)
        self._progress.stop()
        self._progress = None
        self._task_id = None

    def _description(self, stage_name: str) -> str:
        label = _STAGE_LABELS.get(stage_name, stage_name)
        index = min(self._completed + 1, self._expected) if self._expected else 0
        if self._expected:
            return f"阶段 {index}/{self._expected}: {label}"
        return f"阶段: {label}"


__all__ = ["TerminalEventSink"]
