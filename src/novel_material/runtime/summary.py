"""从中立事件汇总运行计数、Token 与诊断。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .contracts import ProgressCounts, RunEvent, RunStatus


@dataclass(frozen=True)
class RunSummarySnapshot:
    stage_counts: dict[str, ProgressCounts] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    diagnostic_counts: dict[str, int] = field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    operation_attempts: int = 0
    operation_completed: int = 0
    estimated_cost: float | None = 0.0
    stage_durations_ms: dict[str, float] = field(default_factory=dict)
    stage_statuses: dict[str, RunStatus] = field(default_factory=dict)


class RunSummaryAccumulator:
    """按 event_id 去重的内存汇总器。"""

    def __init__(self) -> None:
        self._seen_event_ids: set[str] = set()
        self._stage_counts: dict[str, ProgressCounts] = {}
        self._input_tokens = 0
        self._output_tokens = 0
        self._reasoning_tokens = 0
        self._total_tokens = 0
        self._diagnostic_counts: dict[str, int] = {}
        self._started_at: datetime | None = None
        self._completed_at: datetime | None = None
        self._operation_attempts = 0
        self._operation_completed = 0
        self._estimated_cost = 0.0
        self._cost_complete = True
        self._stage_durations_ms: dict[str, float] = {}
        self._stage_statuses: dict[str, RunStatus] = {}

    def consume(self, event: RunEvent) -> None:
        if event.event_id in self._seen_event_ids:
            return
        self._seen_event_ids.add(event.event_id)

        counts = event.attributes.get("counts")
        if isinstance(counts, dict):
            stage_name = event.attributes.get("stage_name")
            completed_stage = (
                event.event_name == "StageCompleted"
                and isinstance(stage_name, str)
                and bool(stage_name)
            )
            key = stage_name if completed_stage else event.stage_id or "run"
            if completed_stage and event.stage_id:
                self._stage_counts.pop(event.stage_id, None)
            self._stage_counts[key] = ProgressCounts.model_validate(counts)

        if event.event_name == "RunStarted":
            self._started_at = event.occurred_at
        elif event.event_name == "RunCompleted":
            self._completed_at = event.occurred_at
        elif event.event_name == "OperationStarted":
            self._operation_attempts += 1
        elif event.event_name == "OperationCompleted":
            self._operation_completed += 1
            self._input_tokens += _non_negative_int(
                event.attributes.get("input_tokens")
            )
            self._output_tokens += _non_negative_int(
                event.attributes.get("output_tokens")
            )
            self._reasoning_tokens += _non_negative_int(
                event.attributes.get("reasoning_tokens_observed")
            )
            self._total_tokens += _non_negative_int(
                event.attributes.get("total_tokens")
            )
            cost = _non_negative_number(event.attributes.get("estimated_cost"))
            if cost is None:
                self._cost_complete = False
            else:
                self._estimated_cost += cost

        if event.event_name == "StageCompleted":
            stage_name = event.attributes.get("stage_name")
            if isinstance(stage_name, str) and stage_name:
                if event.duration_ms is not None:
                    self._stage_durations_ms[stage_name] = event.duration_ms
                if event.status is not None:
                    self._stage_statuses[stage_name] = event.status

        if event.event_name == "DiagnosticRaised":
            code = event.attributes.get("diagnostic_code")
            if isinstance(code, str) and code:
                count = max(_non_negative_int(event.attributes.get("count")), 1)
                self._diagnostic_counts[code] = (
                    self._diagnostic_counts.get(code, 0) + count
                )

    def snapshot(self) -> RunSummarySnapshot:
        return RunSummarySnapshot(
            stage_counts=dict(self._stage_counts),
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            reasoning_tokens=self._reasoning_tokens,
            total_tokens=self._total_tokens,
            diagnostic_counts=dict(self._diagnostic_counts),
            started_at=self._started_at,
            completed_at=self._completed_at,
            operation_attempts=self._operation_attempts,
            operation_completed=self._operation_completed,
            estimated_cost=(self._estimated_cost if self._cost_complete else None),
            stage_durations_ms=dict(self._stage_durations_ms),
            stage_statuses=dict(self._stage_statuses),
        )


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


def _non_negative_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value < 0:
        return None
    return float(value)


__all__ = ["RunSummaryAccumulator", "RunSummarySnapshot"]
