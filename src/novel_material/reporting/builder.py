"""从中立运行事件构建稳定报告。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any

from pydantic import ValidationError

from novel_material.audit.models import ArtifactAudit
from novel_material.runtime.contracts import ProgressCounts, RunEvent, RunStatus
from novel_material.runtime.summary import RunSummaryAccumulator

from .models import (
    ArtifactQualityReport,
    BaselineComparison,
    CharacterQualityReport,
    PipelineRunReport,
    ReleaseGateReport,
    RuntimeMetrics,
    SeverityCounts,
    StageReport,
    WorldbuildingQualityReport,
)


class ReportBuildError(ValueError):
    """事件不足、不一致或携带无效报告数据。"""


def build_run_report(
    events: Iterable[RunEvent],
    *,
    baseline_reports: Iterable[PipelineRunReport] = (),
) -> PipelineRunReport:
    """从一个 run_id 的事件流构建报告。"""
    ordered = _ordered_unique_events(events)
    starts = [item for item in ordered if item.event_name == "RunStarted"]
    if len(starts) != 1:
        raise ReportBuildError("报告要求恰好一个 RunStarted 事件")

    run_id = starts[0].run_id
    if any(item.run_id != run_id for item in ordered):
        raise ReportBuildError("所有事件的 run_id 必须一致")

    completions = [item for item in ordered if item.event_name == "RunCompleted"]
    if not completions:
        raise ReportBuildError("报告要求至少一个 RunCompleted 事件")

    started = starts[0]
    completed = completions[-1]
    if started.material_id is None:
        raise ReportBuildError("RunStarted 缺少 material_id")
    if completed.status is None:
        raise ReportBuildError("RunCompleted 缺少终态 status")

    duration_ms = (completed.occurred_at - started.occurred_at).total_seconds() * 1000
    if duration_ms < 0:
        raise ReportBuildError("RunCompleted 不能早于 RunStarted")

    accumulator = RunSummaryAccumulator()
    for item in ordered:
        try:
            accumulator.consume(item)
        except ValidationError as exc:
            raise ReportBuildError(
                f"{item.event_name} 事件的 counts 无效"
            ) from exc
    snapshot = accumulator.snapshot()

    quality = _artifact_quality(ordered, started.material_id)
    diagnostic_counts = dict(snapshot.diagnostic_counts)
    if quality is None:
        quality = ArtifactQualityReport()
        diagnostic_counts["audit_missing"] = (
            diagnostic_counts.get("audit_missing", 0) + 1
        )

    runtime = RuntimeMetrics(
        operation_attempts=snapshot.operation_attempts,
        operation_completed=snapshot.operation_completed,
        input_tokens=snapshot.input_tokens,
        output_tokens=snapshot.output_tokens,
        reasoning_tokens=snapshot.reasoning_tokens,
        total_tokens=snapshot.total_tokens,
        estimated_cost=snapshot.estimated_cost,
        diagnostic_counts=diagnostic_counts,
    )
    next_actions = _next_actions(quality)

    return PipelineRunReport(
        run_id=run_id,
        material_id=started.material_id,
        command=started.command,
        status=completed.status,
        started_at=started.occurred_at,
        completed_at=completed.occurred_at,
        duration_ms=duration_ms,
        stages=_stage_reports(started, ordered),
        runtime=runtime,
        artifact_quality=quality,
        release_gate=_release_gate_report(ordered),
        baseline=_baseline(
            started.material_id,
            started.command,
            run_id,
            duration_ms,
            baseline_reports,
        ),
        next_actions=next_actions,
    )


def _ordered_unique_events(events: Iterable[RunEvent]) -> list[RunEvent]:
    by_id: dict[str, RunEvent] = {}
    for item in events:
        by_id.setdefault(item.event_id, item)
    return sorted(by_id.values(), key=lambda item: (item.occurred_at, item.event_id))


def _stage_reports(started: RunEvent, events: list[RunEvent]) -> tuple[StageReport, ...]:
    reports: dict[str, StageReport] = {}
    prior = started.attributes.get("report_prior_stages", ())
    if isinstance(prior, (list, tuple)):
        for payload in prior:
            report = _stage_from_mapping(payload)
            if report is not None:
                reports[report.name] = report

    for item in events:
        if item.event_name != "StageCompleted":
            continue
        stage_name = item.attributes.get("stage_name")
        if not isinstance(stage_name, str) or not stage_name:
            continue
        if item.status is None:
            raise ReportBuildError("StageCompleted 事件缺少 status")
        diagnostics = item.attributes.get("diagnostics", ())
        reports[stage_name] = StageReport(
            name=stage_name,
            status=item.status,
            duration_ms=item.duration_ms or 0,
            counts=_counts_dict(item.attributes.get("counts")),
            diagnostic_codes=_diagnostic_codes(diagnostics),
        )
    return tuple(reports.values())


def _stage_from_mapping(payload: object) -> StageReport | None:
    if not isinstance(payload, Mapping):
        return None
    name = payload.get("name")
    status = payload.get("status")
    duration = payload.get("duration_ms", 0)
    if not isinstance(name, str) or not name or status is None:
        return None
    try:
        return StageReport(
            name=name,
            status=status,
            duration_ms=duration,
            counts=_counts_dict(payload.get("counts")),
            diagnostic_codes=_diagnostic_codes(payload.get("diagnostics", ())),
        )
    except ValidationError as exc:
        raise ReportBuildError(f"report_prior_stages 中的阶段无效: {name}") from exc


def _counts_dict(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    try:
        return ProgressCounts.model_validate(value).model_dump(mode="json")
    except ValidationError as exc:
        raise ReportBuildError("阶段 counts 无效") from exc


def _diagnostic_codes(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    codes: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        code = item.get("code")
        if isinstance(code, str) and code:
            codes.append(code)
    return tuple(codes)


def _artifact_quality(
    events: list[RunEvent], material_id: str
) -> ArtifactQualityReport | None:
    audit_events = [
        item for item in events if item.event_name == "ArtifactAuditCompleted"
    ]
    if not audit_events:
        return None
    payload = audit_events[-1].attributes.get("audit")
    try:
        audit = ArtifactAudit.model_validate(payload)
    except ValidationError as exc:
        raise ReportBuildError("ArtifactAuditCompleted.audit 无效") from exc
    if audit.material_id != material_id:
        raise ReportBuildError("ArtifactAuditCompleted.audit 的 material_id 不一致")
    character_quality_payload = (
        payload.get("character_quality") if isinstance(payload, Mapping) else None
    )
    worldbuilding_quality_payload = (
        payload.get("worldbuilding_quality") if isinstance(payload, Mapping) else None
    )
    return ArtifactQualityReport(
        checks=audit.checks,
        character_quality=CharacterQualityReport.model_validate(
            character_quality_payload or {}
        ),
        worldbuilding_quality=WorldbuildingQualityReport.model_validate(
            worldbuilding_quality_payload or {}
        ),
        summary=SeverityCounts.model_validate(audit.summary),
        issues=audit.issues,
        review_budget=audit.review_budget,
    )


def _release_gate_report(events: list[RunEvent]) -> ReleaseGateReport:
    for item in reversed(events):
        if item.event_name != "StageCompleted":
            continue
        if item.attributes.get("stage_name") != "release_gate":
            continue
        outputs = item.attributes.get("outputs")
        if not isinstance(outputs, Mapping):
            return ReleaseGateReport()
        reasons = outputs.get("reasons", ())
        if not isinstance(reasons, (list, tuple)):
            reasons = ()
        return ReleaseGateReport(
            decision=str(outputs.get("decision") or "not_evaluated"),
            release_status=str(outputs.get("release_status") or "unknown"),
            allow_degraded_sync=bool(outputs.get("allow_degraded_sync")),
            override=bool(outputs.get("override")),
            reasons=tuple(str(reason) for reason in reasons if str(reason)),
        )
    return ReleaseGateReport()


def _next_actions(quality: ArtifactQualityReport) -> tuple[str, ...]:
    seen: set[str] = set()
    actions: list[str] = []
    for issue in quality.issues:
        for action in issue.next_actions:
            if action not in seen:
                seen.add(action)
                actions.append(action)
    return tuple(actions)


def _baseline(
    material_id: str,
    command: str,
    run_id: str,
    duration_ms: float,
    reports: Iterable[PipelineRunReport],
) -> BaselineComparison:
    comparable = [
        report
        for report in reports
        if report.run_id != run_id
        and report.material_id == material_id
        and report.command == command
        and report.status is RunStatus.SUCCESS
    ]
    comparable.sort(key=lambda report: report.completed_at, reverse=True)
    recent = comparable[:3]
    if not recent:
        return BaselineComparison()

    baseline_duration = float(median(item.duration_ms for item in recent))
    delta = None
    if baseline_duration > 0:
        delta = (duration_ms - baseline_duration) / baseline_duration * 100
    return BaselineComparison(
        kind="same_material_command",
        baseline_duration_ms=baseline_duration,
        delta_percent=delta,
    )


__all__ = ["ReportBuildError", "build_run_report"]
