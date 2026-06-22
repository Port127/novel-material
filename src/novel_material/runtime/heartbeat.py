"""长任务低频存活事件与可停止后台 worker。"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, Lock, Thread
import time
from typing import Protocol

from .context import RuntimeContext, new_id
from .contracts import RunEvent
from .dispatcher import RuntimeDispatcher


class MonotonicClock(Protocol):
    def monotonic(self) -> float: ...


class _SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()


class HeartbeatEmitter:
    """按显式 RuntimeContext 发布无业务载荷的 heartbeat。"""

    def __init__(
        self,
        *,
        dispatcher: RuntimeDispatcher,
        context: RuntimeContext,
        interval_seconds: float,
        clock: MonotonicClock | None = None,
    ) -> None:
        self.dispatcher = dispatcher
        self.context = context
        self.interval_seconds = max(float(interval_seconds), 0.001)
        self.clock = clock or _SystemClock()
        self.started_at = self.clock.monotonic()
        self.last_emitted_at = self.started_at

    def emit_if_due(self) -> bool:
        now_monotonic = self.clock.monotonic()
        if now_monotonic - self.last_emitted_at < self.interval_seconds:
            return False
        now = datetime.now(timezone.utc)
        self.dispatcher.emit(
            RunEvent(
                event_name="HeartbeatRecorded",
                event_id=new_id("event"),
                occurred_at=now,
                observed_at=now,
                run_id=self.context.run_id,
                stage_id=self.context.stage_id,
                request_id=self.context.request_id,
                provider_request_id=self.context.provider_request_id,
                command=self.context.command,
                component="runtime",
                operation="heartbeat",
                material_id=self.context.material_id,
                attributes={
                    "elapsed_ms": round((now_monotonic - self.started_at) * 1000, 3)
                },
            )
        )
        self.last_emitted_at = now_monotonic
        return True


class HeartbeatWorker:
    """通过可中断等待定期触发 emitter，并在 stop 时回收线程。"""

    def __init__(self, *, emitter: HeartbeatEmitter) -> None:
        self.emitter = emitter
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._lock = Lock()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = Thread(
                target=self._run,
                name=f"heartbeat-{self.emitter.context.run_id}",
                daemon=True,
            )
            self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.wait(self.emitter.interval_seconds):
            self.emitter.emit_if_due()

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            if thread is None:
                return
            self._stop_event.set()
        thread.join(timeout=5)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()


__all__ = ["HeartbeatEmitter", "HeartbeatWorker", "MonotonicClock"]
