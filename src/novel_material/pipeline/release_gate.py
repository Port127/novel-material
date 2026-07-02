"""发布门禁判定逻辑。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import Diagnostic, RunStatus, StageResult


CORE_FAILED_STAGES = {"analyze", "refine", "sync"}
DEGRADED_HOLD_STAGES = {"worldbuilding", "characters", "insights"}
NEXT_ACTIONS_BY_REASON = {
    "audit_blocker": "nm validate artifacts <material_id> --review",
    "audit_error": "nm validate artifacts <material_id> --review",
    "profile_missing": "nm pipeline profile <material_id>",
    "profile_failed": "nm pipeline profile <material_id>",
    "worldbuilding_degraded": "nm pipeline worldbuilding <material_id>",
    "characters_degraded": "nm pipeline characters <material_id>",
    "insights_degraded": "nm pipeline insights <material_id>",
    "analyze_failed": "nm pipeline analyze <material_id>",
    "refine_failed": "nm pipeline refine <material_id>",
    "sync_failed": "nm storage sync <material_id>",
}


def _audit_summary(stage: StageResult | None) -> Mapping:
    if stage is None:
        return {}

    summary = stage.outputs.get("summary")
    if isinstance(summary, Mapping):
        return summary

    audit = stage.outputs.get("audit")
    if isinstance(audit, Mapping):
        nested_summary = audit.get("summary")
        if isinstance(nested_summary, Mapping):
            return nested_summary

    return {}


def evaluate_release_gate(
    material_id: str,
    stages: Iterable[StageResult],
    *,
    mode: str,
    allow_degraded_sync: bool,
) -> StageResult:
    """根据已完成阶段输出决定素材是否允许同步。"""
    items = tuple(stages)
    by_name = {item.name: item for item in items}
    reasons: list[str] = []
    hold_reasons: list[str] = []

    for item in items:
        if item.name in CORE_FAILED_STAGES and item.status is RunStatus.FAILED:
            reasons.append(f"{item.name}_failed")

    audit_summary = _audit_summary(by_name.get("audit"))
    blocker_count = int(audit_summary.get("blocker", 0) or 0)
    error_count = int(audit_summary.get("error", 0) or 0)
    if blocker_count > 0:
        reasons.append("audit_blocker")
    if error_count > 0:
        reasons.append("audit_error")

    if mode in {"standard", "deep"} and by_name.get("profile") is None:
        reasons.append("profile_missing")
    profile = by_name.get("profile")
    if mode in {"standard", "deep"} and profile and profile.status is RunStatus.FAILED:
        reasons.append("profile_failed")

    for item in items:
        if item.name in DEGRADED_HOLD_STAGES and item.status is RunStatus.DEGRADED:
            hold_reasons.append(f"{item.name}_degraded")

    override = False
    if reasons:
        decision = "block"
        release_status = "failed"
        status = RunStatus.FAILED
    elif hold_reasons and allow_degraded_sync:
        decision = "allow"
        release_status = "degraded"
        override = True
        status = RunStatus.SUCCESS
    elif hold_reasons:
        decision = "hold"
        release_status = "degraded"
        status = RunStatus.DEGRADED
    else:
        decision = "allow"
        release_status = "success"
        status = RunStatus.SUCCESS

    next_actions = _next_actions_for_reasons(
        material_id,
        (*reasons, *hold_reasons),
    )

    context = current_context()
    diagnostics = (
        Diagnostic(
            code=(
                "release_gate_held"
                if status is RunStatus.DEGRADED
                else "release_gate_blocked"
            ),
            message="发布门禁未允许默认同步",
            severity="warning" if status is RunStatus.DEGRADED else "error",
            retryable=True,
            next_action="检查 reports/latest.md，修复问题后继续流水线",
        ),
    ) if status is not RunStatus.SUCCESS else ()

    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="release_gate",
        status=status,
        diagnostics=diagnostics,
        outputs={
            "material_id": material_id,
            "decision": decision,
            "release_status": release_status,
            "allow_degraded_sync": allow_degraded_sync,
            "override": override,
            "reasons": tuple(reasons or hold_reasons),
            "next_actions": next_actions,
        },
    )


def _next_actions_for_reasons(
    material_id: str,
    reasons: Iterable[str],
) -> tuple[str, ...]:
    actions: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        template = NEXT_ACTIONS_BY_REASON.get(reason)
        if not template:
            continue
        action = template.replace("<material_id>", material_id)
        if action in seen:
            continue
        seen.add(action)
        actions.append(action)
    return tuple(actions)


__all__ = ["evaluate_release_gate"]
