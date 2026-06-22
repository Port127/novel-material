"""运行事件的同步分发与消费者故障隔离。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol

from .contracts import RunEvent


class SinkCriticality(str, Enum):
    REQUIRED = "required"
    BEST_EFFORT = "best_effort"


class EventSink(Protocol):
    name: str
    criticality: SinkCriticality

    def emit(self, event: RunEvent) -> None: ...


@dataclass(frozen=True)
class DispatchReport:
    delivered: int
    failed_sinks: tuple[str, ...] = ()
    required_failed_sinks: tuple[str, ...] = ()


class RuntimeDispatcher:
    """按注册顺序同步分发事件，并隔离单个 sink 的异常。"""

    def __init__(self, sinks: Iterable[EventSink] = ()):
        self._sinks = tuple(sinks)

    def emit(self, event: RunEvent) -> DispatchReport:
        delivered = 0
        failed: list[str] = []
        required_failed: list[str] = []
        for sink in self._sinks:
            try:
                sink.emit(event)
                delivered += 1
            except Exception:
                failed.append(sink.name)
                if sink.criticality is SinkCriticality.REQUIRED:
                    required_failed.append(sink.name)
        return DispatchReport(
            delivered=delivered,
            failed_sinks=tuple(failed),
            required_failed_sinks=tuple(required_failed),
        )


class NullDispatcher(RuntimeDispatcher):
    """无消费者且无副作用的默认分发器。"""


__all__ = [
    "DispatchReport",
    "EventSink",
    "NullDispatcher",
    "RuntimeDispatcher",
    "SinkCriticality",
]
