"""旧阶段返回值的严格过渡适配。"""

from __future__ import annotations

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import (
    Diagnostic,
    ProgressCounts,
    RunStatus,
    StageResult,
)


def adapt_stage_result(
    name: str,
    value: object,
    *,
    output_key: str | None = None,
) -> StageResult:
    """显式映射旧返回值；False、None 和未知类型永不算成功。"""
    if isinstance(value, StageResult):
        return value

    success = value is True or (
        output_key is not None and isinstance(value, str) and bool(value)
    )
    outputs = {output_key: value} if success and output_key else {}
    diagnostic = () if success else (
        Diagnostic(
            code="legacy_stage_failed",
            message=f"阶段 {name} 返回失败或不受支持的结果: {type(value).__name__}",
            severity="error",
        ),
    )
    context = current_context()
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name=name,
        status=RunStatus.SUCCESS if success else RunStatus.FAILED,
        counts=ProgressCounts(
            expected=1,
            processed=1,
            succeeded=1 if success else 0,
            failed=0 if success else 1,
            remaining=0,
        ),
        diagnostics=diagnostic,
        outputs=outputs,
    )


__all__ = ["adapt_stage_result"]
