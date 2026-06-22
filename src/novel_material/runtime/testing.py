"""Runtime 测试替身。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .context import new_id
from .contracts import RunEvent
from .dispatcher import SinkCriticality


class MemoryEventSink:
    name = "memory"
    criticality = SinkCriticality.BEST_EFFORT

    def __init__(self) -> None:
        self.events: list[RunEvent] = []

    def emit(self, event: RunEvent) -> None:
        self.events.append(event)

    def events_named(self, event_name: str) -> list[RunEvent]:
        return [event for event in self.events if event.event_name == event_name]


class FakeClock:
    def __init__(self, initial: float = 0.0) -> None:
        self._value = initial

    def monotonic(self) -> float:
        return self._value

    def advance(self, seconds: float) -> None:
        self._value += seconds


def event(event_name: str, **overrides: Any) -> RunEvent:
    now = overrides.pop("occurred_at", datetime.now(timezone.utc))
    values: dict[str, Any] = {
        "event_name": event_name,
        "event_id": new_id("event"),
        "occurred_at": now,
        "observed_at": overrides.pop("observed_at", now),
        "run_id": "run-test",
        "command": "pipeline test",
        "component": "runtime",
        "operation": "test",
    }
    values.update(overrides)
    return RunEvent(**values)


__all__ = ["FakeClock", "MemoryEventSink", "event"]
