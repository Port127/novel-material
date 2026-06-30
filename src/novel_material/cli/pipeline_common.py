"""Pipeline CLI 的统一阶段计划构造。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable

from novel_material.audit.budget import ReviewBudget
from novel_material.audit.reviewer import LLMArtifactReviewer
from novel_material.infra.config import NOVELS_DIR, get_settings
from novel_material.infra.logging_config import ensure_log_dir
from novel_material.pipeline.orchestrator import (
    PipelineOrchestrator,
    RunRequest,
    StageSpec,
)
from novel_material.pipeline.progress import inspect_pipeline_state
from novel_material.pipeline.runtime_modes import get_runtime_mode
from novel_material.pipeline.state import PipelineStateStore
from novel_material.pipeline.stage_contracts import adapt_stage_result
from novel_material.pipeline.stages import (
    run_analyze_stage,
    run_artifact_audit_stage,
    run_characters_stage,
    run_evaluation_stage,
    run_ingest_stage,
    run_insights_stage,
    run_outline_stage,
    run_profile_stage,
    run_refine_stage,
    run_tags_stage,
    run_worldbuilding_stage,
)
from novel_material.reporting.sink import ReportSink
from novel_material.run_logging.sink import JsonlSink
from novel_material.runtime.context import new_id
from novel_material.runtime.contracts import (
    RunResult,
    StageResult,
    aggregate_status,
    exit_code_for,
)
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.storage.sync import sync_novel


@dataclass(frozen=True)
class PipelineRuntime:
    """一次 pipeline 命令共享的事件分发器和报告 sink。"""

    dispatcher: RuntimeDispatcher
    report_sink: ReportSink


def _create_pipeline_runtime(
    material_id: str,
    command: str,
    run_id: str,
) -> PipelineRuntime:
    settings = get_settings()
    log_sink = JsonlSink(
        ensure_log_dir(),
        command=command,
        run_id=run_id,
        max_bytes=int(settings["RUN_LOG_MAX_BYTES"]),
    )
    report_sink = ReportSink(NOVELS_DIR / material_id)
    return PipelineRuntime(
        dispatcher=RuntimeDispatcher([log_sink, report_sink]),
        report_sink=report_sink,
    )


def _stage_specs(
    material_id: str,
    options: dict,
    elapsed_provider: Callable[[], float] = lambda: 0.0,
) -> tuple[StageSpec, ...]:
    provider = options.get("provider")
    runtime_mode = get_runtime_mode(options.get("mode", "standard"))
    runtime_mode_name = getattr(runtime_mode, "name", options.get("mode", "standard"))
    insight_limit = runtime_mode.core_insight_chapter_limit
    has_explicit_range = (
        options.get("start") is not None or options.get("end") is not None
    )
    if has_explicit_range:
        insight_start = options.get("start")
        insight_end = options.get("end")
    else:
        insight_start = 1 if insight_limit is not None and insight_limit > 0 else None
        insight_end = insight_limit
    return (
        StageSpec(
            "evaluation",
            lambda _request: run_evaluation_stage(
                material_id,
                provider=provider,
                silent=True,
            ),
            blocking=True,
            enabled=lambda _request: _use_navigation(options),
        ),
        StageSpec(
            "analyze",
            lambda _request: run_analyze_stage(
                material_id,
                start_ch=options.get("start"),
                end_ch=options.get("end"),
                provider=provider,
                use_window=bool(options.get("use_window")),
                skip_embedding=bool(options.get("skip_embedding")),
            ),
            blocking=True,
        ),
        StageSpec(
            "outline",
            lambda _request: run_outline_stage(material_id, provider=provider),
            blocking=False,
        ),
        StageSpec(
            "worldbuilding",
            lambda _request: run_worldbuilding_stage(
                material_id,
                provider=provider,
            ),
            blocking=False,
        ),
        StageSpec(
            "characters",
            lambda _request: run_characters_stage(
                material_id,
                provider=provider,
            ),
            blocking=False,
        ),
        StageSpec(
            "tags",
            lambda _request: run_tags_stage(material_id, provider=provider),
            blocking=False,
        ),
        StageSpec(
            "insights",
            lambda _request: run_insights_stage(
                material_id,
                start_ch=insight_start,
                end_ch=insight_end,
                provider=provider,
            ),
            blocking=False,
            enabled=lambda _request: runtime_mode.include_core_insights,
        ),
        StageSpec(
            "refine",
            lambda _request: run_refine_stage(material_id),
            blocking=True,
        ),
        StageSpec(
            "profile",
            lambda _request: run_profile_stage(material_id, provider=provider),
            blocking=False,
            enabled=lambda _request: runtime_mode_name in {"standard", "deep"},
        ),
        StageSpec(
            "audit",
            lambda _request: _audit_stage(
                material_id,
                options,
                elapsed_provider,
            ),
            blocking=True,
        ),
        StageSpec(
            "sync",
            lambda _request: sync_novel(
                material_id,
                provider=provider,
                use_window=bool(options.get("use_window")),
                repair_allowed=False,
            ),
            blocking=True,
            enabled=lambda _request: not bool(options.get("skip_sync")),
        ),
    )


def _use_navigation(options: dict) -> bool:
    """判断本次统一流水线是否执行前置导航。"""
    if options.get("use_navigation") is True:
        return True
    if options.get("skip_navigation") is True:
        return False
    return get_runtime_mode(options.get("mode", "standard")).name in {
        "standard",
        "deep",
    }


def _audit_stage(
    material_id: str,
    options: dict,
    elapsed_provider: Callable[[], float],
) -> StageResult:
    mode = get_runtime_mode(options.get("mode", "standard"))
    if mode.name == "fast":
        return run_artifact_audit_stage(material_id)

    settings = get_settings()
    max_calls_key = (
        "ARTIFACT_REVIEW_MAX_CALLS_DEEP"
        if mode.name == "deep"
        else "ARTIFACT_REVIEW_MAX_CALLS_STANDARD"
    )
    budget = ReviewBudget(
        max_seconds=max(
            0.0,
            elapsed_provider()
            * float(settings["ARTIFACT_REVIEW_TIME_FRACTION_STANDARD"]),
        ),
        max_calls=int(settings[max_calls_key]),
        clock=time.monotonic,
    )
    return run_artifact_audit_stage(
        material_id,
        reviewer=LLMArtifactReviewer(),
        budget=budget,
    )


def run_full_pipeline(
    *,
    runtime_observer: Callable[[PipelineRuntime], None] | None = None,
    **options,
) -> RunResult:
    run_id = new_id("run")
    started_at = datetime.now(timezone.utc)
    run_start = time.monotonic()
    ingest = run_ingest_stage(options["file_path"])
    ingest = ingest.model_copy(
        update={
            "duration_ms": max(0.0, (time.monotonic() - run_start) * 1000),
        }
    )
    if ingest.status.value == "failed":
        return RunResult.from_stages(run_id, "pipeline full", [ingest])
    material_id = str(ingest.outputs["material_id"])
    runtime = _create_pipeline_runtime(material_id, "pipeline full", run_id)
    if runtime_observer is not None:
        runtime_observer(runtime)
    request = RunRequest(
        run_id=run_id,
        command="pipeline full",
        material_id=material_id,
        started_at=started_at,
        options={**options, "report_prior_stages": (ingest,)},
    )
    state_store = PipelineStateStore(NOVELS_DIR / material_id)
    with state_store.acquire_lease(run_id):
        remainder = PipelineOrchestrator(
            _stage_specs(
                material_id,
                options,
                elapsed_provider=lambda: time.monotonic() - run_start,
            ),
            dispatcher=runtime.dispatcher,
            state_store=state_store,
            prior_stages=(ingest,),
        ).run(request)
    return combine_run_result(
        (ingest,),
        remainder,
        expected_stages=1 + remainder.counts.expected,
    )


def run_continue_pipeline(
    *,
    material_id: str,
    runtime_observer: Callable[[PipelineRuntime], None] | None = None,
    **options,
) -> RunResult:
    run_start = time.monotonic()
    run_id = new_id("run")
    inspection = inspect_pipeline_state(material_id, novels_dir=NOVELS_DIR)
    plan = PipelineOrchestrator.plan_continue(
        inspection,
        include_navigation=_use_navigation(options),
    )
    if not inspection.exists:
        missing = adapt_stage_result("status", None)
        return RunResult.from_stages(run_id, "pipeline continue", [missing])
    runtime = _create_pipeline_runtime(material_id, "pipeline continue", run_id)
    if runtime_observer is not None:
        runtime_observer(runtime)
    specs = tuple(
        spec
        for spec in _stage_specs(
            material_id,
            options,
            elapsed_provider=lambda: time.monotonic() - run_start,
        )
        if spec.name in plan.stage_names
    )
    request = RunRequest(
        run_id=run_id,
        command="pipeline continue",
        material_id=material_id,
        options=options,
    )
    state_store = PipelineStateStore(NOVELS_DIR / material_id)
    prior_stages = tuple(
        stage
        for name, stage in inspection.stages.items()
        if name not in plan.stage_names
    )
    with state_store.acquire_lease(run_id):
        return PipelineOrchestrator(
            specs,
            dispatcher=runtime.dispatcher,
            state_store=state_store,
            prior_stages=prior_stages,
        ).run(request)


def combine_run_result(
    prior_stages: Iterable[StageResult],
    remainder: RunResult,
    *,
    expected_stages: int,
) -> RunResult:
    """合并 full 的 ingest 与后续结果，并保留顶层可观测性诊断。"""
    combined = RunResult.from_stages(
        remainder.run_id,
        remainder.command,
        (*tuple(prior_stages), *remainder.stages),
        expected_stages=expected_stages,
    )
    extra_diagnostics = tuple(
        item
        for item in remainder.diagnostics
        if item not in combined.diagnostics
    )
    status = aggregate_status((combined.status, remainder.status))
    return combined.model_copy(
        update={
            "status": status,
            "exit_code": exit_code_for(status),
            "diagnostics": (*combined.diagnostics, *extra_diagnostics),
        }
    )


__all__ = [
    "PipelineRuntime",
    "combine_run_result",
    "run_continue_pipeline",
    "run_full_pipeline",
]
