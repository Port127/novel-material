"""Validation helpers for chapter insight YAML."""

from __future__ import annotations

from novel_material.analysis_profiles import AnalysisProfile, load_profiles, merge_profiles
from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml
from novel_material.pipeline.profile_resolver import resolve_profile_names

COMMON_FIELD_NAMES = {
    "core_event",
    "scene_goal",
    "conflict",
    "stakes",
    "turning_point",
    "reader_hook",
    "character_change",
    "writing_takeaway",
}


def validate_insight(insight: dict, profile: AnalysisProfile) -> list[str]:
    """Validate one chapter insight against a merged profile."""
    errors: list[str] = []

    if insight.get("schema_version") != "1.0":
        errors.append("schema_version 必须为 1.0")

    common = insight.get("common")
    if not isinstance(common, dict):
        errors.append("common 必须是对象")
        common = {}

    genre = insight.get("genre")
    if not isinstance(genre, dict):
        errors.append("genre 必须是对象")
        genre = {}

    for name, field in profile.required_fields.items():
        container = common if name in COMMON_FIELD_NAMES else genre
        value = container.get(name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"缺少必填字段: {name}")
            continue
        if field.min_length is not None and len(value) < field.min_length:
            errors.append(f"{name} 过短: {len(value)} < {field.min_length}")
        if field.max_length is not None and len(value) > field.max_length:
            errors.append(f"{name} 过长: {len(value)} > {field.max_length}")

    evidence = insight.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence 至少需要 1 条")
    else:
        for index, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                errors.append(f"evidence[{index}] 必须是对象")
                continue
            for key in ("field", "source", "text"):
                value = item.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"evidence[{index}].{key} 不能为空")
            text = item.get("text")
            if isinstance(text, str) and len(text) > 120:
                errors.append(f"evidence[{index}].text 过长: {len(text)} > 120")

    confidence = insight.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append("confidence 必须是 0.0-1.0 的数字")

    return errors


def validate_material_insights(material_id: str) -> list[str]:
    """Validate all generated chapter insight files for one material."""
    novel_dir = NOVELS_DIR / material_id
    meta_file = novel_dir / "meta.yaml"
    meta = load_yaml(meta_file) if meta_file.exists() else {}
    profile = merge_profiles(load_profiles(resolve_profile_names(meta)))
    insights_dir = novel_dir / "chapter_insights"
    if not insights_dir.exists():
        return [f"chapter_insights 不存在: {insights_dir}"]

    errors: list[str] = []
    for path in sorted(insights_dir.glob("*.yaml")):
        insight = load_yaml(path)
        for error in validate_insight(insight, profile):
            errors.append(f"{path.name}: {error}")
    return errors
