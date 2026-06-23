"""产物审计规则编排与 StageResult 适配。"""

from __future__ import annotations

from pathlib import Path

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import Diagnostic, ProgressCounts, StageResult

from .models import ArtifactAudit, ArtifactIssue, AuditSeverity, audit_run_status
from .rules import RULES, AuditContext


_SEVERITY_PRIORITY = {
    AuditSeverity.BLOCKER: 0,
    AuditSeverity.ERROR: 1,
    AuditSeverity.WARNING: 2,
    AuditSeverity.INFO: 3,
}


def audit_material(
    material_id: str,
    *,
    novels_dir: Path | None = None,
) -> ArtifactAudit:
    """运行全部确定性规则，并对问题去重和稳定排序。"""
    if novels_dir is None:
        from novel_material.infra.config import NOVELS_DIR

        novels_dir = NOVELS_DIR
    context = AuditContext(material_id, Path(novels_dir) / material_id)
    checks: list[str] = []
    issues_by_key: dict[tuple[str, str, str], ArtifactIssue] = {}
    for name, rule in RULES:
        checks.append(name)
        for issue in rule(context):
            key = (issue.code, issue.artifact, issue.message)
            issues_by_key.setdefault(key, issue)

    issues = tuple(
        sorted(
            issues_by_key.values(),
            key=lambda item: (
                _SEVERITY_PRIORITY[item.severity],
                item.code,
                item.artifact,
            ),
        )
    )
    return ArtifactAudit(
        material_id=material_id,
        checks=tuple(checks),
        issues=issues,
    )


def audit_to_stage_result(audit: ArtifactAudit) -> StageResult:
    """把审计结论转换为流水线统一阶段结果。"""
    status = audit_run_status(audit)
    diagnostics = tuple(
        Diagnostic(
            code=issue.code,
            message=issue.message,
            severity=issue.severity.value,
            next_action=issue.next_actions[0] if issue.next_actions else None,
        )
        for issue in audit.issues
        if issue.severity in {AuditSeverity.BLOCKER, AuditSeverity.ERROR}
    )
    context = current_context()
    checks_count = len(audit.checks)
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="audit",
        status=status,
        counts=ProgressCounts(
            expected=checks_count,
            processed=checks_count,
            remaining=0,
        ),
        diagnostics=diagnostics,
        outputs={"audit": audit.model_dump(mode="json")},
    )


__all__ = ["audit_material", "audit_to_stage_result"]
