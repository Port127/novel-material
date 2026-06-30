"""统一 Pipeline 阶段计划、结果聚合与运行事件发布。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from novel_material.runtime.context import current_context, new_id, run_context, stage_context
from novel_material.runtime.contracts import (
    Diagnostic,
    ExitCode,
    RunEvent,
    RunResult,
    RunStatus,
    StageResult,
)
from novel_material.runtime.dispatcher import NullDispatcher, RuntimeDispatcher
from novel_material.pipeline.state import PersistedRunState, PipelineStateStore


class StageContractError(TypeError):
    """阶段入口违反 StageResult 契约。"""


@dataclass(frozen=True)
class RunRequest:
    run_id: str
    command: str
    material_id: str | None = None
    started_at: datetime | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageSpec:
    name: str
    execute: Callable[[RunRequest], StageResult]
    blocking: bool
    enabled: Callable[[RunRequest], bool] = lambda _request: True


@dataclass(frozen=True)
class PipelinePlan:
    stage_names: tuple[str, ...]

    @property
    def first_stage(self) -> str | None:
        return self.stage_names[0] if self.stage_names else None


class PipelineOrchestrator:
    def __init__(
        self,
        stages: Iterable[StageSpec],
        *,
        dispatcher: RuntimeDispatcher | None = None,
        state_store: PipelineStateStore | None = None,
        prior_stages: Iterable[StageResult] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._stages = tuple(stages)
        self._dispatcher = dispatcher or NullDispatcher()
        self._state_store = state_store
        self._prior_stages = tuple(prior_stages)
        self._clock = clock

    @staticmethod
    def plan_continue(inspection, *, include_navigation: bool = False) -> PipelinePlan:
        """从首个非成功阶段开始重跑其全部下游阶段。"""
        if not inspection.exists:
            return PipelinePlan(())
        order = (
            (("evaluation",) if include_navigation else ())
            + (
                "analyze",
                "outline",
                "worldbuilding",
                "characters",
                "tags",
                "insights",
                "refine",
                "profile",
                "audit",
                "sync",
            )
        )
        for index, name in enumerate(order):
            stage = inspection.stages.get(name)
            if stage is None or stage.status is not RunStatus.SUCCESS:
                return PipelinePlan(order[index:])
        return PipelinePlan(())

    def run(self, request: RunRequest) -> RunResult:
        enabled = tuple(spec for spec in self._stages if spec.enabled(request))
        required_failures: set[str] = set()
        results: list[StageResult] = []
        created_at = request.started_at or datetime.now(timezone.utc)
        generation = 1

        self._persist(
            request,
            status=RunStatus.RUNNING,
            stages=results,
            generation=generation,
            created_at=created_at,
        )

        with run_context(
            command=request.command,
            material_id=request.material_id,
            run_id=request.run_id,
            dispatcher=self._dispatcher,
        ):
            required_failures.update(
                self._emit(
                    "RunStarted",
                    occurred_at=request.started_at,
                    attributes={
                        "report_prior_stages": _report_prior_stages(request),
                    },
                )
            )
            for spec in enabled:
                with stage_context(spec.name):
                    required_failures.update(
                        self._emit(
                            "StageStarted",
                            attributes={"stage_name": spec.name},
                        )
                    )
                    stage_started = self._clock()
                    try:
                        result = spec.execute(request)
                    except KeyboardInterrupt:
                        result = StageResult(
                            stage_id=current_context().stage_id or new_id("stage"),
                            name=spec.name,
                            status=RunStatus.INTERRUPTED,
                            diagnostics=(
                                Diagnostic(
                                    code="user_interrupted",
                                    message="用户中断运行",
                                    severity="warning",
                                    retryable=True,
                                ),
                            ),
                        )
                    except Exception as exc:
                        result = StageResult(
                            stage_id=current_context().stage_id or new_id("stage"),
                            name=spec.name,
                            status=RunStatus.FAILED,
                            diagnostics=(
                                Diagnostic(
                                    code="stage_unhandled_exception",
                                    message=(
                                        f"阶段 {spec.name} 未处理异常: "
                                        f"{type(exc).__name__}"
                                    ),
                                    severity="error",
                                    retryable=True,
                                ),
                            ),
                        )
                    duration_ms = max(0.0, (self._clock() - stage_started) * 1000)
                    if not isinstance(result, StageResult):
                        raise StageContractError(
                            f"阶段 {spec.name} 必须返回 StageResult，实际为 {type(result).__name__}"
                        )
                    result = result.model_copy(update={"duration_ms": duration_ms})
                    results.append(result)
                    generation += 1
                    self._persist(
                        request,
                        status=result.status,
                        stages=results,
                        generation=generation,
                        created_at=created_at,
                    )
                    required_failures.update(
                        self._emit(
                            "StageCompleted",
                            status=result.status,
                            duration_ms=result.duration_ms,
                            attributes={
                                "stage_name": spec.name,
                                "counts": result.counts.model_dump(mode="json"),
                                "diagnostics": [
                                    item.model_dump(mode="json")
                                    for item in result.diagnostics
                                ],
                            },
                        )
                    )
                if result.status is RunStatus.INTERRUPTED or (
                    spec.blocking and result.status is RunStatus.FAILED
                ):
                    break

            run_result = RunResult.from_stages(
                run_id=request.run_id,
                command=request.command,
                stages=results,
                expected_stages=len(enabled),
            )
            if required_failures and run_result.status is RunStatus.SUCCESS:
                run_result = _with_observability_degradation(
                    run_result,
                    required_failures,
                )
            final_failures = self._emit(
                "RunCompleted",
                status=run_result.status,
                attributes={
                    "counts": run_result.counts.model_dump(mode="json"),
                    "diagnostics": [
                        item.model_dump(mode="json")
                        for item in run_result.diagnostics
                    ],
                },
            )
            if final_failures and run_result.status is RunStatus.SUCCESS:
                run_result = _with_observability_degradation(
                    run_result,
                    set(final_failures),
                )
            generation += 1
            self._persist(
                request,
                status=run_result.status,
                stages=results,
                generation=generation,
                created_at=created_at,
            )
            return run_result

    def _persist(
        self,
        request: RunRequest,
        *,
        status: RunStatus,
        stages: list[StageResult],
        generation: int,
        created_at: datetime,
    ) -> None:
        if self._state_store is None:
            return
        self._state_store.write(
            PersistedRunState(
                run_id=request.run_id,
                command=request.command,
                status=status,
                generation=generation,
                created_at=created_at,
                updated_at=datetime.now(timezone.utc),
                stages=self._merge_persisted_stages(stages),
            )
        )

    def _merge_persisted_stages(
        self,
        stages: list[StageResult],
    ) -> tuple[StageResult, ...]:
        merged = {stage.name: stage for stage in self._prior_stages}
        merged.update((stage.name, stage) for stage in stages)
        return tuple(merged.values())

    def _emit(
        self,
        event_name: str,
        *,
        status: RunStatus | None = None,
        duration_ms: float | None = None,
        attributes: dict[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> tuple[str, ...]:
        context = current_context()
        if context is None:
            return ()
        now = datetime.now(timezone.utc)
        report = self._dispatcher.emit(
            RunEvent(
                event_name=event_name,
                event_id=new_id("event"),
                occurred_at=occurred_at or now,
                observed_at=now,
                run_id=context.run_id,
                stage_id=context.stage_id,
                command=context.command,
                component="pipeline",
                operation="orchestrate",
                material_id=context.material_id,
                status=status,
                duration_ms=duration_ms,
                attributes=attributes or {},
            )
        )
        return report.required_failed_sinks


def _report_prior_stages(request: RunRequest) -> list[dict[str, Any]]:
    value = request.options.get("report_prior_stages", ())
    if not isinstance(value, (list, tuple)):
        return []
    return [
        {
            "name": stage.name,
            "status": stage.status.value,
            "duration_ms": stage.duration_ms,
            "counts": stage.counts.model_dump(mode="json"),
            "diagnostics": [
                item.model_dump(mode="json") for item in stage.diagnostics
            ],
        }
        for stage in value
        if isinstance(stage, StageResult)
    ]


def _with_observability_degradation(
    result: RunResult,
    failed_sinks: set[str],
) -> RunResult:
    diagnostic = Diagnostic(
        code="event_sink_failed",
        message=f"required sink 写入失败: {', '.join(sorted(failed_sinks))}",
        severity="warning",
        retryable=True,
    )
    return result.model_copy(
        update={
            "status": RunStatus.DEGRADED,
            "exit_code": ExitCode.DEGRADED,
            "diagnostics": (*result.diagnostics, diagnostic),
        }
    )


def render_next_actions(result: RunResult, material_id: str) -> tuple[str, ...]:
    """为非成功运行生成可直接执行的恢复命令。"""
    if result.status not in {RunStatus.DEGRADED, RunStatus.FAILED, RunStatus.INTERRUPTED}:
        return ()
    return (
        f"python -m novel_material.cli.main pipeline status {material_id}",
        f"python -m novel_material.cli.main pipeline continue {material_id}",
    )


__all__ = [
    "PipelineOrchestrator",
    "PipelinePlan",
    "RunRequest",
    "StageContractError",
    "StageSpec",
    "render_next_actions",
]
