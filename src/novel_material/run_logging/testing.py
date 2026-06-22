"""结构化日志测试 sink。"""

from __future__ import annotations

from novel_material.runtime.contracts import RunEvent
from novel_material.runtime.dispatcher import SinkCriticality


class MemoryLogSink:
    name = "memory-log"
    criticality = SinkCriticality.BEST_EFFORT

    def __init__(self) -> None:
        self.events: list[RunEvent] = []

    def emit(self, event: RunEvent) -> None:
        self.events.append(event)


__all__ = ["MemoryLogSink"]
