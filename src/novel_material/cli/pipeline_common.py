"""Pipeline CLI 的统一阶段计划构造。"""

from __future__ import annotations

from novel_material.infra.config import NOVELS_DIR
from novel_material.pipeline.orchestrator import PipelineOrchestrator, RunRequest, StageSpec
from novel_material.pipeline.progress import inspect_pipeline_state
from novel_material.pipeline.runtime_modes import get_runtime_mode
from novel_material.pipeline.state import PipelineStateStore
from novel_material.pipeline.stage_contracts import adapt_stage_result
from novel_material.pipeline.stages import (
    run_analyze_stage,
    run_characters_stage,
    run_evaluation_stage,
    run_ingest_stage,
    run_insights_stage,
    run_outline_stage,
    run_refine_stage,
    run_tags_stage,
    run_worldbuilding_stage,
)
from novel_material.runtime.context import new_id
from novel_material.runtime.contracts import RunResult
from novel_material.storage.sync import sync_novel


def _stage_specs(material_id: str, options: dict) -> tuple[StageSpec, ...]:
    provider = options.get("provider")
    return (
        StageSpec(
            "evaluation",
            lambda _request: run_evaluation_stage(material_id, provider=provider, silent=True),
            blocking=True,
            enabled=lambda _request: bool(options.get("use_window")),
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
        StageSpec("outline", lambda _request: run_outline_stage(material_id, provider=provider), blocking=False),
        StageSpec("worldbuilding", lambda _request: run_worldbuilding_stage(material_id, provider=provider), blocking=False),
        StageSpec("characters", lambda _request: run_characters_stage(material_id, provider=provider), blocking=False),
        StageSpec("tags", lambda _request: run_tags_stage(material_id, provider=provider), blocking=False),
        StageSpec(
            "insights",
            lambda _request: run_insights_stage(material_id, provider=provider),
            blocking=False,
            enabled=lambda _request: get_runtime_mode(options.get("mode", "standard")).include_core_insights,
        ),
        StageSpec("refine", lambda _request: run_refine_stage(material_id), blocking=True),
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


def run_full_pipeline(**options) -> RunResult:
    run_id = new_id("run")
    ingest = run_ingest_stage(options["file_path"])
    if ingest.status.value == "failed":
        return RunResult.from_stages(run_id, "pipeline full", [ingest])
    material_id = str(ingest.outputs["material_id"])
    request = RunRequest(run_id=run_id, command="pipeline full", material_id=material_id, options=options)
    state_store = PipelineStateStore(NOVELS_DIR / material_id)
    with state_store.acquire_lease(run_id):
        remainder = PipelineOrchestrator(
            _stage_specs(material_id, options),
            state_store=state_store,
            prior_stages=(ingest,),
        ).run(request)
    return RunResult.from_stages(
        run_id,
        "pipeline full",
        [ingest, *remainder.stages],
        expected_stages=1 + remainder.counts.expected,
    )


def run_continue_pipeline(*, material_id: str, **options) -> RunResult:
    run_id = new_id("run")
    inspection = inspect_pipeline_state(material_id, novels_dir=NOVELS_DIR)
    plan = PipelineOrchestrator.plan_continue(inspection)
    specs = tuple(
        spec for spec in _stage_specs(material_id, options)
        if spec.name in plan.stage_names
    )
    if not inspection.exists:
        missing = adapt_stage_result("status", None)
        return RunResult.from_stages(run_id, "pipeline continue", [missing])
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
            state_store=state_store,
            prior_stages=prior_stages,
        ).run(request)


__all__ = ["run_continue_pipeline", "run_full_pipeline"]
