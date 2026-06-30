"""将中立运行事件渲染为终端进度。"""

from __future__ import annotations

from novel_material.runtime.contracts import RunEvent
from novel_material.runtime.dispatcher import SinkCriticality

from .modes import TerminalMode
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

    def _stage_started(self, event: RunEvent) -> None:
        stage_name = str(event.attributes.get("stage_name") or event.operation)
        self._current_stage = stage_name
        description = self._description(stage_name)
        self._reporter.progress(
            description=description,
            completed=self._completed,
            total=self._expected,
        )

    def _stage_completed(self, event: RunEvent) -> None:
        stage_name = str(
            event.attributes.get("stage_name")
            or self._current_stage
            or event.operation
        )
        description = self._description(stage_name)
        self._completed += 1
        self._reporter.progress(
            description=description,
            completed=self._completed,
            total=self._expected,
        )

    def _stop(self) -> None:
        return

    def _description(self, stage_name: str) -> str:
        label = _STAGE_LABELS.get(stage_name, stage_name)
        index = min(self._completed + 1, self._expected) if self._expected else 0
        if self._expected:
            return f"阶段 {index}/{self._expected}: {label}"
        return f"阶段: {label}"


__all__ = ["TerminalEventSink"]
