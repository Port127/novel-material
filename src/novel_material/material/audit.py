"""素材变更操作的最小结构化审计事件。"""

from datetime import datetime, timezone

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import RunEvent, RunStatus
from novel_material.runtime.dispatcher import RuntimeDispatcher


def emit_material_audit(
    dispatcher: RuntimeDispatcher,
    *,
    operation: str,
    object_id: str,
    phase: str,
    status: RunStatus | None = None,
) -> None:
    context = current_context()
    if context is None:
        return
    now = datetime.now(timezone.utc)
    dispatcher.emit(
        RunEvent(
            event_name="AuditRecorded",
            event_id=new_id("event"),
            occurred_at=now,
            observed_at=now,
            run_id=context.run_id,
            stage_id=context.stage_id,
            command=context.command,
            component="material",
            operation=operation,
            material_id=context.material_id,
            status=status,
            attributes={
                "phase": phase,
                "object_type": "material",
                "object_id": object_id,
            },
        )
    )


__all__ = ["emit_material_audit"]
