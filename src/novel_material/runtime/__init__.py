"""运行事件、上下文与结果契约。"""

from .contracts import (
    Diagnostic,
    ExitCode,
    ProgressCounts,
    RunEvent,
    RunResult,
    RunStatus,
    StageResult,
    aggregate_status,
    exit_code_for,
)

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
