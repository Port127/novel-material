"""基于真实批次耗时的稳健 ETA。"""

from __future__ import annotations

from dataclasses import dataclass
import statistics
from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float: ...


@dataclass(frozen=True)
class EtaSnapshot:
    elapsed_seconds: float
    remaining_seconds: float | None


class BatchEtaEstimator:
    def __init__(self, *, clock: Clock, min_samples: int = 2, window: int = 5):
        self.clock = clock
        self.min_samples = max(1, min_samples)
        self.window = max(1, window)
        self.total = 0
        self.started_at = 0.0
        self._last_batch_at = 0.0
        self._seconds_per_item: list[float] = []

    def start(self, *, total: int, completed: int = 0) -> None:
        self.total = max(total, completed)
        self.started_at = self.clock.monotonic()
        self._last_batch_at = self.started_at
        self._seconds_per_item.clear()

    def complete_batch(self, *, items: int) -> None:
        now = self.clock.monotonic()
        duration = now - self._last_batch_at
        if items > 0 and duration > 0:
            self._seconds_per_item.append(duration / items)
            self._seconds_per_item = self._seconds_per_item[-self.window:]
        self._last_batch_at = now

    def snapshot(self, *, completed: int) -> EtaSnapshot:
        elapsed = max(self.clock.monotonic() - self.started_at, 0)
        if len(self._seconds_per_item) < self.min_samples:
            return EtaSnapshot(elapsed, None)
        rate = statistics.median(self._seconds_per_item)
        remaining = max(self.total - completed, 0) * rate
        return EtaSnapshot(elapsed, remaining)


__all__ = ["BatchEtaEstimator", "EtaSnapshot"]
