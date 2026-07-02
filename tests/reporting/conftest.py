from datetime import datetime, timedelta, timezone

import pytest

from novel_material.audit.models import (
    ArtifactAudit,
    ArtifactIssue,
    AuditSeverity,
    ReviewBudgetUsage,
    ReviewState,
)
from novel_material.reporting.models import (
    ArtifactQualityReport,
    BaselineComparison,
    CharacterQualityReport,
    PipelineRunReport,
    RuntimeMetrics,
    SeverityCounts,
    StageReport,
    WorldbuildingQualityReport,
)
from novel_material.runtime.contracts import RunStatus
from novel_material.runtime.testing import event


@pytest.fixture
def sample_report() -> PipelineRunReport:
    return PipelineRunReport(
        run_id="run-test",
        material_id="nm_demo",
        command="pipeline full",
        status=RunStatus.DEGRADED,
        started_at=datetime(2026, 6, 23, 1, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 6, 23, 1, 0, 20, tzinfo=timezone.utc),
        duration_ms=20000,
        stages=(
            StageReport(
                name="audit",
                status=RunStatus.DEGRADED,
                duration_ms=10000,
                counts={"expected": 1, "processed": 1, "succeeded": 0},
                diagnostic_codes=("artifact_quality_degraded",),
            ),
        ),
        runtime=RuntimeMetrics(
            operation_attempts=2,
            operation_completed=1,
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost=0.02,
            diagnostic_counts={"artifact_quality_degraded": 1},
        ),
        artifact_quality=ArtifactQualityReport(
            checks=("characters", "worldbuilding"),
            character_quality=CharacterQualityReport(
                biography_target_count=5,
                biography_completed_count=4,
                brief_profile_count=3,
                biography_failed_count=1,
                full_profile_count=2,
                enriched_profile_count=1,
                partial_profile_count=1,
                fallback_profile_count=1,
                repair_attempted_count=2,
                repair_succeeded_count=1,
                repair_failed_count=1,
            ),
            worldbuilding_quality=WorldbuildingQualityReport(
                layout="layered",
                entity_count=8,
                relation_count=6,
                evidence_count=21,
                broken_relation_count=1,
                missing_evidence_count=2,
                dimension_status={"locations": "stats_seeded"},
                source_quality_counts={"llm_verified": 7, "stats_seeded": 1},
            ),
            summary=SeverityCounts(
                error=1,
                warning=1,
                not_reviewed_due_to_budget=1,
            ),
            issues=(
                ArtifactIssue(
                    code="budget_review_pending",
                    severity=AuditSeverity.WARNING,
                    artifact="worldbuilding/_index.yaml",
                    message="待复审内容含 sk-secret-value",
                    evidence={"api_key": "API Key must not leak"},
                    next_actions=("nm pipeline worldbuilding nm_demo",),
                    reviewable=True,
                    review_state=ReviewState.NOT_REVIEWED_DUE_TO_BUDGET,
                ),
                ArtifactIssue(
                    code="character_profile_fallback",
                    severity=AuditSeverity.ERROR,
                    artifact="characters/profiles/主角.yaml",
                    message="主要人物为空壳",
                    next_actions=(
                        "nm pipeline characters nm_demo --repair-character 主角",
                    ),
                ),
            ),
            review_budget=ReviewBudgetUsage(
                mode="standard",
                max_seconds=10,
                elapsed_seconds=8,
                max_calls=2,
                calls_used=2,
                stop_reason="budget_exhausted",
            ),
        ),
        baseline=BaselineComparison(
            kind="same_material_command",
            baseline_duration_ms=10000,
            delta_percent=100,
        ),
        next_actions=(
            "nm pipeline worldbuilding nm_demo",
            "nm pipeline characters nm_demo --repair-character 主角",
        ),
    )


@pytest.fixture
def sample_events(sample_report: PipelineRunReport):
    started_at = sample_report.started_at
    audit = ArtifactAudit(
        material_id=sample_report.material_id,
        checks=sample_report.artifact_quality.checks,
        issues=sample_report.artifact_quality.issues,
        character_quality=sample_report.artifact_quality.character_quality.model_dump(
            mode="json"
        ),
        worldbuilding_quality=sample_report.artifact_quality.worldbuilding_quality.model_dump(
            mode="json"
        ),
        review_budget=sample_report.artifact_quality.review_budget,
    )
    return [
        event(
            "RunStarted",
            occurred_at=started_at,
            command=sample_report.command,
            material_id=sample_report.material_id,
        ),
        event(
            "OperationStarted",
            occurred_at=started_at + timedelta(seconds=1),
            command=sample_report.command,
            material_id=sample_report.material_id,
        ),
        event(
            "OperationCompleted",
            occurred_at=started_at + timedelta(seconds=2),
            command=sample_report.command,
            material_id=sample_report.material_id,
            attributes={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "estimated_cost": 0.02,
            },
        ),
        event(
            "ArtifactAuditCompleted",
            occurred_at=started_at + timedelta(seconds=3),
            command=sample_report.command,
            material_id=sample_report.material_id,
            status=RunStatus.DEGRADED,
            attributes={"audit": audit.model_dump(mode="json")},
        ),
        event(
            "RunCompleted",
            occurred_at=sample_report.completed_at,
            command=sample_report.command,
            material_id=sample_report.material_id,
            status=sample_report.status,
            attributes={"counts": {}, "diagnostics": []},
        ),
    ]
