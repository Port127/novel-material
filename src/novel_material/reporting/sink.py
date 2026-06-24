"""在 RunCompleted 时生成并持久化报告的 required sink。"""

from __future__ import annotations

from pathlib import Path

from novel_material.runtime.contracts import RunEvent
from novel_material.runtime.dispatcher import SinkCriticality

from .builder import build_run_report
from .models import PipelineRunReport
from .writer import ReportPaths, ReportWriter


class ReportSink:
    """按 run_id 缓存事件，并在运行完成时写入报告。"""

    name = "report"
    criticality = SinkCriticality.REQUIRED

    def __init__(self, novel_dir: Path) -> None:
        self.writer = ReportWriter(novel_dir)
        self.latest_report: PipelineRunReport | None = None
        self.latest_paths: ReportPaths | None = None
        self._events: dict[str, dict[str, RunEvent]] = {}

    def emit(self, event: RunEvent) -> None:
        run_events = self._events.setdefault(event.run_id, {})
        run_events.setdefault(event.event_id, event)
        if event.event_name != "RunCompleted":
            return

        history = self.writer.load_history()
        report = build_run_report(
            run_events.values(),
            baseline_reports=history,
        )
        paths = self.writer.write(report)
        self.latest_report = report
        self.latest_paths = paths


__all__ = ["ReportSink"]
