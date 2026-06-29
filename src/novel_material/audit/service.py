"""产物审计规则编排与 StageResult 适配。"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import Diagnostic, ProgressCounts, StageResult
from novel_material.infra.yaml_io import load_yaml

from .budget import ReviewBudget
from .models import (
    ArtifactAudit,
    ArtifactIssue,
    AuditSeverity,
    CharacterQualitySummary,
    ReviewBudgetUsage,
    ReviewState,
    audit_run_status,
)
from .reviewer import ArtifactReviewer
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
    reviewer: ArtifactReviewer | None = None,
    budget: ReviewBudget | None = None,
    estimated_call_seconds: float | None = None,
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

    issues = _sort_issues(issues_by_key.values())
    review_usage = ReviewBudgetUsage(mode="rules_only")
    if reviewer is not None and budget is not None:
        issues = _review_issues(
            issues,
            context=context,
            reviewer=reviewer,
            budget=budget,
            estimated_call_seconds=estimated_call_seconds,
        )
        review_usage = budget.snapshot(mode="llm_review")
    return ArtifactAudit(
        material_id=material_id,
        checks=tuple(checks),
        issues=issues,
        character_quality=_summarize_character_quality(context),
        review_budget=review_usage,
    )


def _sort_issues(issues: Iterable[ArtifactIssue]) -> tuple[ArtifactIssue, ...]:
    return tuple(
        sorted(
            issues,
            key=lambda item: (
                _SEVERITY_PRIORITY[item.severity],
                item.code,
                item.artifact,
            ),
        )
    )


def _summarize_character_quality(context: AuditContext) -> CharacterQualitySummary:
    index = load_yaml(context.novel_dir / "characters" / "_index.yaml")
    profiles_dir = context.novel_dir / "characters" / "profiles"
    profiles: list[dict] = []
    if profiles_dir.is_dir():
        profiles = [load_yaml(path) for path in sorted(profiles_dir.glob("*.yaml"))]

    targets = index.get("biography_targets")
    target_names = [
        item.get("name")
        for item in targets
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ] if isinstance(targets, list) else []
    target_count = _non_negative_int(
        index.get("biography_target_count"),
        fallback=len(target_names),
    )
    completed_count = sum(
        1
        for profile in profiles
        if profile.get("profile_level") == "full"
        and profile.get("biography_complete") is True
        and (
            not target_names
            or (
                isinstance(profile.get("name"), str)
                and profile.get("name") in target_names
            )
        )
    )
    if target_count and completed_count > target_count:
        completed_count = target_count

    return CharacterQualitySummary(
        biography_target_count=target_count,
        biography_completed_count=completed_count,
        brief_profile_count=sum(
            1 for profile in profiles if profile.get("profile_level") == "brief"
        ),
        biography_failed_count=_non_negative_int(index.get("biography_failed_count")),
    )


def _non_negative_int(value: object, *, fallback: int = 0) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return fallback


def _review_issues(
    issues: tuple[ArtifactIssue, ...],
    *,
    context: AuditContext,
    reviewer: ArtifactReviewer,
    budget: ReviewBudget,
    estimated_call_seconds: float | None,
) -> tuple[ArtifactIssue, ...]:
    if estimated_call_seconds is None:
        from novel_material.infra.config import get_settings

        estimated_call_seconds = float(
            get_settings()["ARTIFACT_REVIEW_ESTIMATED_CALL_SECONDS"]
        )
    evidence_chars = getattr(reviewer, "evidence_chars", None)
    if evidence_chars is None:
        from novel_material.infra.config import get_settings

        evidence_chars = int(get_settings()["ARTIFACT_REVIEW_EVIDENCE_CHARS"])

    candidates = [
        issue
        for issue in issues
        if issue.reviewable and issue.review_state is ReviewState.PENDING
    ]
    replacements: dict[tuple[str, str, str], ArtifactIssue] = {}
    review_failures: list[ArtifactIssue] = []
    for index, issue in enumerate(candidates):
        if not budget.reserve(estimated_seconds=estimated_call_seconds):
            for remaining in candidates[index:]:
                replacements[_issue_key(remaining)] = remaining.model_copy(
                    update={
                        "review_state": ReviewState.NOT_REVIEWED_DUE_TO_BUDGET,
                    }
                )
            break

        try:
            decision = reviewer.review(
                issue,
                _read_evidence_excerpt(
                    context.novel_dir,
                    issue.artifact,
                    max_chars=evidence_chars,
                ),
            )
            if decision.code != issue.code:
                raise ValueError("review decision code 与问题不一致")
        except Exception as exc:
            review_failures.append(
                ArtifactIssue(
                    code="review_failed",
                    severity=AuditSeverity.WARNING,
                    artifact=issue.artifact,
                    message=f"可疑项 {issue.code} 复审失败",
                    evidence={"error_type": type(exc).__name__},
                )
            )
            continue

        evidence = {**issue.evidence, "review_rationale": decision.rationale}
        replacements[_issue_key(issue)] = issue.model_copy(
            update={
                "severity": (
                    issue.severity if decision.confirmed else AuditSeverity.INFO
                ),
                "evidence": evidence,
                "review_state": (
                    ReviewState.CONFIRMED
                    if decision.confirmed
                    else ReviewState.DISMISSED
                ),
            }
        )

    reviewed = [replacements.get(_issue_key(issue), issue) for issue in issues]
    return _sort_issues((*reviewed, *review_failures))


def _issue_key(issue: ArtifactIssue) -> tuple[str, str, str]:
    return issue.code, issue.artifact, issue.message


def _read_evidence_excerpt(
    novel_dir: Path,
    artifact: str,
    *,
    max_chars: int,
) -> str:
    root = novel_dir.resolve()
    path = (novel_dir / artifact).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[:max_chars]


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
