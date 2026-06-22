"""同步事件分发与消费者故障隔离测试。"""

from __future__ import annotations

from novel_material.runtime.dispatcher import (
    RuntimeDispatcher,
    SinkCriticality,
)
from novel_material.runtime.testing import MemoryEventSink, event


class FailingSink:
    def __init__(self, name: str, criticality: SinkCriticality):
        self.name = name
        self.criticality = criticality

    def emit(self, _event):
        raise OSError("disk full")


def test_failing_sink_does_not_block_healthy_sink():
    healthy = MemoryEventSink()
    broken = FailingSink("broken", SinkCriticality.REQUIRED)

    report = RuntimeDispatcher([broken, healthy]).emit(event("RunStarted"))

    assert len(healthy.events) == 1
    assert report.delivered == 1
    assert report.failed_sinks == ("broken",)
    assert report.required_failed_sinks == ("broken",)


def test_best_effort_sink_failure_is_not_required_failure():
    preview = FailingSink("preview", SinkCriticality.BEST_EFFORT)

    report = RuntimeDispatcher([preview]).emit(event("RunStarted"))

    assert report.failed_sinks == ("preview",)
    assert report.required_failed_sinks == ()

