"""业务运行、阶段结果与中立事件契约。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RunStatus(str, Enum):
    """运行或阶段的统一状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class ExitCode(IntEnum):
    """CLI 稳定退出码。"""

    SUCCESS = 0
    FAILED = 1
    USAGE = 2
    DEGRADED = 3
    INTERRUPTED = 130


class ProgressCounts(BaseModel):
    """同一计数单位内的处理与结果数量。"""

    model_config = ConfigDict(frozen=True)

    expected: int = Field(default=0, ge=0)
    processed: int = Field(default=0, ge=0)
    succeeded: int = Field(default=0, ge=0)
    degraded: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    remaining: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> "ProgressCounts":
        if self.processed > self.expected:
            raise ValueError("processed 不能大于 expected")
        if self.succeeded + self.degraded + self.failed > self.processed:
            raise ValueError("结果计数不能大于 processed")
        if self.remaining != self.expected - self.processed:
            raise ValueError("remaining 必须等于 expected - processed")
        return self


class Diagnostic(BaseModel):
    """供日志、终端与自动恢复共同消费的稳定诊断。"""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    count: int = Field(default=1, ge=1)
    retryable: bool = False
    next_action: str | None = None


class StageResult(BaseModel):
    """单个业务阶段的最终结果。"""

    model_config = ConfigDict(frozen=True)

    stage_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    status: RunStatus
    counts: ProgressCounts = Field(default_factory=ProgressCounts)
    duration_ms: float = Field(default=0, ge=0)
    diagnostics: tuple[Diagnostic, ...] = ()


class RunResult(BaseModel):
    """一次 CLI 运行的唯一完成结论。"""

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    command: str = Field(min_length=1)
    status: RunStatus
    exit_code: ExitCode
    stages: tuple[StageResult, ...] = ()
    counts: ProgressCounts = Field(default_factory=ProgressCounts)
    diagnostics: tuple[Diagnostic, ...] = ()

    @classmethod
    def from_stages(
        cls,
        run_id: str,
        command: str,
        stages: Iterable[StageResult],
        expected_stages: int | None = None,
    ) -> "RunResult":
        stage_items = tuple(stages)
        expected = len(stage_items) if expected_stages is None else expected_stages
        if expected < len(stage_items):
            raise ValueError("expected_stages 不能小于已处理阶段数")

        status = aggregate_status(stage.status for stage in stage_items)
        return cls(
            run_id=run_id,
            command=command,
            status=status,
            exit_code=exit_code_for(status),
            stages=stage_items,
            counts=ProgressCounts(
                expected=expected,
                processed=len(stage_items),
                succeeded=sum(stage.status is RunStatus.SUCCESS for stage in stage_items),
                degraded=sum(stage.status is RunStatus.DEGRADED for stage in stage_items),
                failed=sum(stage.status is RunStatus.FAILED for stage in stage_items),
                remaining=expected - len(stage_items),
            ),
            diagnostics=tuple(
                diagnostic
                for stage in stage_items
                for diagnostic in stage.diagnostics
            ),
        )


class RunEvent(BaseModel):
    """日志与终端消费者共享的中立运行事件。"""

    model_config = ConfigDict(frozen=True)

    schema_version: int = Field(default=1, ge=1)
    event_name: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    occurred_at: datetime
    observed_at: datetime
    severity_text: str = "INFO"
    severity_number: int = Field(default=9, ge=1, le=24)
    run_id: str = Field(min_length=1)
    stage_id: str | None = None
    request_id: str | None = None
    provider_request_id: str | None = None
    command: str = Field(min_length=1)
    component: str = Field(min_length=1)
    operation: str = Field(min_length=1)
    material_id: str | None = None
    status: RunStatus | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at", "observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("时间字段必须包含时区")
        return value


_STATUS_PRIORITY = (
    RunStatus.FAILED,
    RunStatus.INTERRUPTED,
    RunStatus.DEGRADED,
    RunStatus.RUNNING,
    RunStatus.PENDING,
    RunStatus.SUCCESS,
)


def aggregate_status(statuses: Iterable[RunStatus]) -> RunStatus:
    """按固定优先级聚合阶段状态；空集合表示无工作且成功。"""
    status_set = set(statuses)
    if not status_set:
        return RunStatus.SUCCESS
    return next(status for status in _STATUS_PRIORITY if status in status_set)


def exit_code_for(status: RunStatus) -> ExitCode:
    """将最终运行状态映射为稳定退出码。"""
    if status is RunStatus.SUCCESS:
        return ExitCode.SUCCESS
    if status is RunStatus.DEGRADED:
        return ExitCode.DEGRADED
    if status is RunStatus.INTERRUPTED:
        return ExitCode.INTERRUPTED
    return ExitCode.FAILED


__all__ = [
    "Diagnostic",
    "ExitCode",
    "ProgressCounts",
    "RunEvent",
    "RunResult",
    "RunStatus",
    "StageResult",
    "aggregate_status",
    "exit_code_for",
]
