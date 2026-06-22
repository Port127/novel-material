"""长任务 heartbeat 生命周期测试。"""

from __future__ import annotations

from novel_material.runtime.context import RuntimeContext
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.runtime.heartbeat import HeartbeatEmitter, HeartbeatWorker
from novel_material.runtime.testing import FakeClock, MemoryEventSink


def runtime_context() -> RuntimeContext:
    return RuntimeContext(
        run_id="run-1",
        command="pipeline full",
        material_id="nm_demo",
        stage_id="stage-1",
    )


def test_heartbeat_uses_explicit_context_without_business_payload():
    sink = MemoryEventSink()
    clock = FakeClock()
    emitter = HeartbeatEmitter(
        dispatcher=RuntimeDispatcher([sink]),
        context=runtime_context(),
        clock=clock,
        interval_seconds=60,
    )

    clock.advance(60)
    assert emitter.emit_if_due() is True

    heartbeat = sink.events_named("HeartbeatRecorded")[-1]
    assert heartbeat.run_id == "run-1"
    assert heartbeat.stage_id == "stage-1"
    assert set(heartbeat.attributes) == {"elapsed_ms"}


def test_heartbeat_worker_stop_joins_thread():
    worker = HeartbeatWorker(
        emitter=HeartbeatEmitter(
            dispatcher=RuntimeDispatcher(),
            context=runtime_context(),
            clock=FakeClock(),
            interval_seconds=60,
        )
    )

    worker.start()
    worker.stop()

    assert worker.is_alive() is False
    worker.stop()  # 重复停止保持幂等
