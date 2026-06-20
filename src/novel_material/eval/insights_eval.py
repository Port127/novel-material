"""Deterministic scoring for genre-aware chapter insights."""

from __future__ import annotations

GENERIC_PHRASES = ("剧情精彩", "人物饱满", "节奏紧凑", "人物生动")


def _contains_all(text: object, keywords: list[str]) -> bool:
    if not isinstance(text, str):
        return False
    return all(keyword in text for keyword in keywords)


def _rate(hits: int, total: int) -> float:
    return round(hits / total, 4) if total else 1.0


def score_insight_case(case: dict, insight: dict) -> dict[str, float]:
    """Score one insight against a deterministic eval case."""
    expected_profiles = case.get("expected_profiles", [])
    actual_profiles = insight.get("profiles", [])
    profile_hits = sum(1 for profile in expected_profiles if profile in actual_profiles)

    expected_fields = case.get("expected_fields", {})
    field_total = 0
    field_present = 0
    keyword_total = 0
    keyword_hits = 0

    for section, fields in expected_fields.items():
        section_data = insight.get(section, {})
        if not isinstance(section_data, dict):
            section_data = {}
        for rule_name, keywords in fields.items():
            field_name = rule_name.removesuffix("_contains")
            value = section_data.get(field_name)
            field_total += 1
            if isinstance(value, str) and value.strip():
                field_present += 1
            keyword_total += 1
            if _contains_all(value, list(keywords)):
                keyword_hits += 1

    evidence = insight.get("evidence")
    has_evidence = isinstance(evidence, list) and len(evidence) > 0
    quality = insight.get("quality") if isinstance(insight.get("quality"), dict) else {}
    repaired = bool(quality.get("repaired"))
    validation_errors = quality.get("validation_errors", [])
    invalid_after_repair = repaired and bool(validation_errors)

    all_text = " ".join(
        str(value)
        for section in ("common", "genre", "optional")
        if isinstance(insight.get(section), dict)
        for value in insight[section].values()
    )
    generic = any(phrase in all_text for phrase in GENERIC_PHRASES)

    return {
        "field_presence_rate": _rate(field_present, field_total),
        "keyword_hit_rate": _rate(keyword_hits, keyword_total),
        "evidence_presence_rate": 1.0 if has_evidence else 0.0,
        "profile_resolution_accuracy": _rate(profile_hits, len(expected_profiles)),
        "repair_rate": 1.0 if repaired else 0.0,
        "invalid_after_repair_rate": 1.0 if invalid_after_repair else 0.0,
        "generic_phrase_rate": 1.0 if generic else 0.0,
    }
