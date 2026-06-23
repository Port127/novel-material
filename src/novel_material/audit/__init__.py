"""小说分析产物的只读质量审计契约。"""

from .models import (
    ArtifactAudit,
    ArtifactIssue,
    AuditSeverity,
    ReviewBudgetUsage,
    ReviewState,
    audit_run_status,
)


def __getattr__(name: str):
    """按需导入服务入口，保持审计契约包导入无文件读取副作用。"""
    if name in {"audit_material", "audit_to_stage_result"}:
        from .service import audit_material, audit_to_stage_result

        exports = {
            "audit_material": audit_material,
            "audit_to_stage_result": audit_to_stage_result,
        }
        value = exports[name]
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ArtifactAudit",
    "ArtifactIssue",
    "AuditSeverity",
    "ReviewBudgetUsage",
    "ReviewState",
    "audit_material",
    "audit_run_status",
    "audit_to_stage_result",
]
