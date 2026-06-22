"""重复诊断的明细限流与结束汇总。"""

from __future__ import annotations

from dataclasses import dataclass, field

from novel_material.runtime.context import new_id
from novel_material.runtime.contracts import RunEvent
from novel_material.runtime.dispatcher import EventSink


@dataclass
class _DiagnosticState:
    template: RunEvent
    count: int = 0
    samples: list[str] = field(default_factory=list)


class DiagnosticAggregator:
    def __init__(self, sink: EventSink, *, detail_limit: int, sample_limit: int = 3):
        self.sink = sink
        self.name = f"diagnostic-aggregator:{sink.name}"
        self.criticality = sink.criticality
        self.detail_limit = max(0, detail_limit)
        self.sample_limit = max(0, sample_limit)
        self._states: dict[tuple[str, str | None, str], _DiagnosticState] = {}

    def emit(self, source: RunEvent) -> None:
        if source.event_name != "DiagnosticRaised":
            self.sink.emit(source)
            return
        code = source.attributes.get("diagnostic_code")
        if not isinstance(code, str) or not code:
            self.sink.emit(source)
            return
        key = (source.run_id, source.stage_id, code)
        state = self._states.setdefault(key, _DiagnosticState(template=source))
        state.count += 1
        message = source.attributes.get("message")
        if isinstance(message, str) and len(state.samples) < self.sample_limit:
            state.samples.append(message)
        if state.count <= self.detail_limit:
            self.sink.emit(source)

    def flush(self) -> None:
        for (_run_id, _stage_id, code), state in self._states.items():
            attributes = {
                "diagnostic_code": code,
                "total_count": state.count,
                "samples": list(state.samples),
            }
            self.sink.emit(
                state.template.model_copy(
                    update={
                        "event_name": "DiagnosticSummaryRecorded",
                        "event_id": new_id("event"),
                        "attributes": attributes,
                    }
                )
            )
        self._states.clear()


__all__ = ["DiagnosticAggregator"]
