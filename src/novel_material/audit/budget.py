"""可选 LLM 复审的时间与调用次数预算。"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from .models import ReviewBudgetUsage


@dataclass
class ReviewBudget:
    """一次审计内不可恢复的双重预算。"""

    max_seconds: float
    max_calls: int
    clock: Callable[[], float] = time.monotonic
    calls_used: int = field(default=0, init=False)
    stop_reason: str | None = field(default=None, init=False)
    _started_at: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_seconds < 0:
            raise ValueError("max_seconds 不能小于 0")
        if self.max_calls < 0:
            raise ValueError("max_calls 不能小于 0")

    def reserve(self, *, estimated_seconds: float) -> bool:
        """在预计不会越过任一上限时预留一次调用。"""
        if estimated_seconds < 0:
            raise ValueError("estimated_seconds 不能小于 0")
        if self.stop_reason is not None:
            return False

        now = self.clock()
        if self._started_at is None:
            self._started_at = now
        if self.calls_used >= self.max_calls:
            self.stop_reason = "call_budget_exhausted"
            return False
        if self._elapsed(now) + estimated_seconds > self.max_seconds:
            self.stop_reason = "time_budget_exhausted"
            return False

        self.calls_used += 1
        return True

    def snapshot(self, *, mode: str) -> ReviewBudgetUsage:
        """返回供审计报告持久化的当前预算快照。"""
        elapsed = 0.0 if self._started_at is None else self._elapsed(self.clock())
        return ReviewBudgetUsage(
            mode=mode,
            max_seconds=self.max_seconds,
            elapsed_seconds=elapsed,
            max_calls=self.max_calls,
            calls_used=self.calls_used,
            stop_reason=self.stop_reason,
        )

    def _elapsed(self, now: float) -> float:
        if self._started_at is None:
            return 0.0
        return max(0.0, now - self._started_at)


__all__ = ["ReviewBudget"]
