"""统一 Pipeline 阶段计划、结果聚合与运行事件发布。"""

from __future__ import annotations

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


class StageContractError(TypeError):
    """阶段入口违反 StageResult 契约。"""


@dataclass(frozen=True)
class RunRequest:
    run_id: str
    command: str
    material_id: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageSpec:
    name: str
    execute: Callable[[RunRequest], StageResult]
    blocking: bool
    enabled: Callable[[RunRequest], bool] = lambda _request: True


class PipelineOrchestrator:
    def __init__(
        self,
        stages: Iterable[StageSpec],
        *,
        dispatcher: RuntimeDispatcher | None = None,
    ) -> None:
        self._stages = tuple(stages)
        self._dispatcher = dispatcher or NullDispatcher()

    def run(self, request: RunRequest) -> RunResult:
        enabled = tuple(spec for spec in self._stages if spec.enabled(request))
        required_failures: set[str] = set()
        results: list[StageResult] = []

        with run_context(
            command=request.command,
            material_id=request.material_id,
            run_id=request.run_id,
        ):
            required_failures.update(self._emit("RunStarted"))
            for spec in enabled:
                with stage_context(spec.name):
                    required_failures.update(self._emit("StageStarted"))
                    result = spec.execute(request)
                    if not isinstance(result, StageResult):
                        raise StageContractError(
                            f"阶段 {spec.name} 必须返回 StageResult，实际为 {type(result).__name__}"
                        )
                    results.append(result)
                    required_failures.update(
                        self._emit("StageCompleted", status=result.status)
                    )
                if spec.blocking and result.status is RunStatus.FAILED:
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
            final_failures = self._emit("RunCompleted", status=run_result.status)
            if final_failures and run_result.status is RunStatus.SUCCESS:
                run_result = _with_observability_degradation(
                    run_result,
                    set(final_failures),
                )
            return run_result

    def _emit(
        self,
        event_name: str,
        *,
        status: RunStatus | None = None,
    ) -> tuple[str, ...]:
        context = current_context()
        if context is None:
            return ()
        now = datetime.now(timezone.utc)
        report = self._dispatcher.emit(
            RunEvent(
                event_name=event_name,
                event_id=new_id("event"),
                occurred_at=now,
                observed_at=now,
                run_id=context.run_id,
                stage_id=context.stage_id,
                command=context.command,
                component="pipeline",
                operation="orchestrate",
                material_id=context.material_id,
                status=status,
            )
        )
        return report.required_failed_sinks


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


__all__ = [
    "PipelineOrchestrator",
    "RunRequest",
    "StageContractError",
    "StageSpec",
]
