"""人物档案质量分级与诊断字段工具。"""

from __future__ import annotations

from typing import Any

QUALITY_LEVELS = ("full", "enriched", "partial", "fallback")


def classify_profile_quality(profile: dict[str, Any]) -> str:
    """返回人物档案质量等级，未知等级按 partial 处理。"""
    level = profile.get("profile_level")
    if level in QUALITY_LEVELS:
        return str(level)
    if profile.get("biography_complete") is True:
        return "full"
    if profile.get("schema_issues"):
        return "partial"
    return "fallback"


def build_character_quality_counts(
    profiles: list[dict[str, Any]],
) -> dict[str, int]:
    """统计人物档案质量分布。"""
    counts = {level: 0 for level in QUALITY_LEVELS}
    for profile in profiles:
        counts[classify_profile_quality(profile)] += 1
    return counts


def mark_schema_issue(
    profile: dict[str, Any],
    *,
    issue: str,
    level: str,
    source_quality: str,
    repair_attempts: int,
) -> dict[str, Any]:
    """给档案添加 schema 诊断信息，返回新 dict。"""
    result = dict(profile)
    issues = list(result.get("schema_issues") or [])
    issues.append(issue)
    result["schema_issues"] = issues
    result["profile_level"] = level
    result["source_quality"] = source_quality
    result["repair_attempts"] = repair_attempts
    if level != "full":
        result["biography_complete"] = False
    return result


__all__ = [
    "QUALITY_LEVELS",
    "build_character_quality_counts",
    "classify_profile_quality",
    "mark_schema_issue",
]
