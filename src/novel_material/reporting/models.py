"""稳定、不可变的流水线运行报告模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from novel_material.audit.models import ArtifactIssue, ReviewBudgetUsage
from novel_material.runtime.contracts import RunStatus


class SeverityCounts(BaseModel):
    """产物问题的严重程度汇总。"""

    model_config = ConfigDict(frozen=True)

    blocker: int = Field(default=0, ge=0)
    error: int = Field(default=0, ge=0)
    warning: int = Field(default=0, ge=0)
    info: int = Field(default=0, ge=0)
    not_reviewed_due_to_budget: int = Field(default=0, ge=0)


class RuntimeMetrics(BaseModel):
    """一次运行的调用、Token、成本和诊断统计。"""

    model_config = ConfigDict(frozen=True)

    operation_attempts: int = Field(default=0, ge=0)
    operation_completed: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    diagnostic_counts: dict[str, int] = Field(default_factory=dict)


class StageReport(BaseModel):
    """报告中的单阶段摘要，不包含领域产物正文。"""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    status: RunStatus
    duration_ms: float = Field(ge=0)
    counts: dict[str, Any] = Field(default_factory=dict)
    diagnostic_codes: tuple[str, ...] = ()


class CharacterQualityReport(BaseModel):
    """人物小传质量汇总，不包含人物正文。"""

    model_config = ConfigDict(frozen=True)

    biography_target_count: int = Field(default=0, ge=0)
    biography_completed_count: int = Field(default=0, ge=0)
    brief_profile_count: int = Field(default=0, ge=0)
    biography_failed_count: int = Field(default=0, ge=0)
    full_profile_count: int = Field(default=0, ge=0)
    enriched_profile_count: int = Field(default=0, ge=0)
    partial_profile_count: int = Field(default=0, ge=0)
    fallback_profile_count: int = Field(default=0, ge=0)
    repair_attempted_count: int = Field(default=0, ge=0)
    repair_succeeded_count: int = Field(default=0, ge=0)
    repair_failed_count: int = Field(default=0, ge=0)


class WorldbuildingQualityReport(BaseModel):
    """世界观结构质量汇总，不包含世界观正文。"""

    model_config = ConfigDict(frozen=True)

    layout: str | None = None
    entity_count: int = Field(default=0, ge=0)
    relation_count: int = Field(default=0, ge=0)
    evidence_count: int = Field(default=0, ge=0)
    broken_relation_count: int = Field(default=0, ge=0)
    missing_evidence_count: int = Field(default=0, ge=0)


class ArtifactQualityReport(BaseModel):
    """产物审计结论及其复审预算使用情况。"""

    model_config = ConfigDict(frozen=True)

    checks: tuple[str, ...] = ()
    character_quality: CharacterQualityReport = Field(
        default_factory=CharacterQualityReport
    )
    worldbuilding_quality: WorldbuildingQualityReport = Field(
        default_factory=WorldbuildingQualityReport
    )
    summary: SeverityCounts = Field(default_factory=SeverityCounts)
    issues: tuple[ArtifactIssue, ...] = ()
    review_budget: ReviewBudgetUsage = Field(default_factory=ReviewBudgetUsage)


class ReleaseGateReport(BaseModel):
    """发布门禁摘要，不包含领域正文。"""

    model_config = ConfigDict(frozen=True)

    decision: str = "not_evaluated"
    release_status: str = "unknown"
    allow_degraded_sync: bool = False
    override: bool = False
    reasons: tuple[str, ...] = ()


class BaselineComparison(BaseModel):
    """与可比较历史运行的耗时比较。"""

    model_config = ConfigDict(frozen=True)

    kind: str = "unavailable"
    baseline_duration_ms: float | None = Field(default=None, ge=0)
    delta_percent: float | None = None


class PipelineRunReport(BaseModel):
    """一次流水线执行的完整、可持久化报告。"""

    model_config = ConfigDict(frozen=True)

    schema_version: int = Field(default=1, ge=1)
    run_id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)
    command: str = Field(min_length=1)
    status: RunStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0)
    stages: tuple[StageReport, ...] = ()
    runtime: RuntimeMetrics = Field(default_factory=RuntimeMetrics)
    artifact_quality: ArtifactQualityReport = Field(
        default_factory=ArtifactQualityReport
    )
    release_gate: ReleaseGateReport = Field(default_factory=ReleaseGateReport)
    baseline: BaselineComparison = Field(default_factory=BaselineComparison)
    next_actions: tuple[str, ...] = ()


__all__ = [
    "ArtifactQualityReport",
    "BaselineComparison",
    "CharacterQualityReport",
    "PipelineRunReport",
    "ReleaseGateReport",
    "RuntimeMetrics",
    "SeverityCounts",
    "StageReport",
    "WorldbuildingQualityReport",
]
