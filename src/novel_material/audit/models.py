"""产物审计的问题、预算和汇总模型。"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from novel_material.runtime.contracts import RunStatus


class AuditSeverity(str, Enum):
    """产物问题对流水线结果的影响等级。"""

    BLOCKER = "blocker"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReviewState(str, Enum):
    """可疑项的可选 LLM 复审状态。"""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    NOT_REVIEWED_DUE_TO_BUDGET = "not_reviewed_due_to_budget"


class ArtifactIssue(BaseModel):
    """一个可定位、可审计并可给出后续动作的产物问题。"""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    severity: AuditSeverity
    artifact: str = Field(min_length=1)
    message: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    next_actions: tuple[str, ...] = ()
    reviewable: bool = False
    review_state: ReviewState = ReviewState.NOT_REQUIRED


class ReviewBudgetUsage(BaseModel):
    """一次审计实际使用的复审预算。"""

    model_config = ConfigDict(frozen=True)

    mode: str = "rules_only"
    max_seconds: float = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    max_calls: int = Field(default=0, ge=0)
    calls_used: int = Field(default=0, ge=0)
    stop_reason: str | None = None


class CharacterQualitySummary(BaseModel):
    """人物小传质量信号，供审计事件和运行报告复用。"""

    model_config = ConfigDict(frozen=True)

    biography_target_count: int = Field(default=0, ge=0)
    biography_completed_count: int = Field(default=0, ge=0)
    brief_profile_count: int = Field(default=0, ge=0)
    biography_failed_count: int = Field(default=0, ge=0)


class ArtifactAudit(BaseModel):
    """一部素材的完整产物审计结论。"""

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    material_id: str = Field(min_length=1)
    checks: tuple[str, ...] = ()
    issues: tuple[ArtifactIssue, ...] = ()
    character_quality: CharacterQualitySummary = Field(
        default_factory=CharacterQualitySummary
    )
    review_budget: ReviewBudgetUsage = Field(default_factory=ReviewBudgetUsage)

    @computed_field
    @property
    def summary(self) -> dict[str, int]:
        """按严重程度和预算跳过状态汇总问题数量。"""
        counts = {severity.value: 0 for severity in AuditSeverity}
        counts[ReviewState.NOT_REVIEWED_DUE_TO_BUDGET.value] = 0
        for item in self.issues:
            counts[item.severity.value] += 1
            if item.review_state is ReviewState.NOT_REVIEWED_DUE_TO_BUDGET:
                counts[ReviewState.NOT_REVIEWED_DUE_TO_BUDGET.value] += 1
        return counts


def audit_run_status(audit: ArtifactAudit) -> RunStatus:
    """把最高审计严重程度映射到稳定运行状态。"""
    severities = {item.severity for item in audit.issues}
    if AuditSeverity.BLOCKER in severities:
        return RunStatus.FAILED
    if AuditSeverity.ERROR in severities:
        return RunStatus.DEGRADED
    return RunStatus.SUCCESS


__all__ = [
    "ArtifactAudit",
    "ArtifactIssue",
    "AuditSeverity",
    "CharacterQualitySummary",
    "ReviewBudgetUsage",
    "ReviewState",
    "audit_run_status",
]
