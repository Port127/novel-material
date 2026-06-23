from novel_material.audit.models import (
    ArtifactAudit,
    ArtifactIssue,
    AuditSeverity,
    audit_run_status,
)
from novel_material.runtime.contracts import RunStatus


def issue(code: str, severity: AuditSeverity) -> ArtifactIssue:
    return ArtifactIssue(
        code=code,
        severity=severity,
        artifact="characters/profiles/主角.yaml",
        message="档案不完整",
        evidence={"missing_fields": ["arc_summary"]},
        next_actions=("nm pipeline characters nm_demo --repair-character 主角",),
    )


def test_audit_status_maps_blocker_error_and_warning():
    assert audit_run_status(ArtifactAudit(material_id="nm_demo")) is RunStatus.SUCCESS
    assert audit_run_status(
        ArtifactAudit(
            material_id="nm_demo",
            issues=(issue("sparse", AuditSeverity.WARNING),),
        )
    ) is RunStatus.SUCCESS
    assert audit_run_status(
        ArtifactAudit(
            material_id="nm_demo",
            issues=(issue("fallback", AuditSeverity.ERROR),),
        )
    ) is RunStatus.DEGRADED
    assert audit_run_status(
        ArtifactAudit(
            material_id="nm_demo",
            issues=(issue("missing", AuditSeverity.BLOCKER),),
        )
    ) is RunStatus.FAILED


def test_audit_dump_is_stable_and_contains_summary_counts():
    audit = ArtifactAudit(
        material_id="nm_demo",
        checks=("required_files", "characters"),
        issues=(
            issue("fallback", AuditSeverity.ERROR),
            issue("sparse", AuditSeverity.WARNING),
        ),
    )

    payload = audit.model_dump(mode="json")

    assert payload["schema_version"] == 1
    assert payload["summary"] == {
        "blocker": 0,
        "error": 1,
        "warning": 1,
        "info": 0,
        "not_reviewed_due_to_budget": 0,
    }
