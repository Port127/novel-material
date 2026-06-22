"""从中立事件汇总运行计数、Token 与诊断。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .contracts import ProgressCounts, RunEvent


@dataclass(frozen=True)
class RunSummarySnapshot:
    stage_counts: dict[str, ProgressCounts] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    diagnostic_counts: dict[str, int] = field(default_factory=dict)


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

    def consume(self, event: RunEvent) -> None:
        if event.event_id in self._seen_event_ids:
            return
        self._seen_event_ids.add(event.event_id)

        counts = event.attributes.get("counts")
        if isinstance(counts, dict):
            key = event.stage_id or "run"
            self._stage_counts[key] = ProgressCounts.model_validate(counts)

        self._input_tokens += _non_negative_int(event.attributes.get("input_tokens"))
        self._output_tokens += _non_negative_int(event.attributes.get("output_tokens"))
        self._reasoning_tokens += _non_negative_int(
            event.attributes.get("reasoning_tokens_observed")
        )
        self._total_tokens += _non_negative_int(event.attributes.get("total_tokens"))

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
        )


def _non_negative_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


__all__ = ["RunSummaryAccumulator", "RunSummarySnapshot"]
