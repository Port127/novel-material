"""Resolve analysis profiles from novel metadata."""

from __future__ import annotations

from novel_material.tags.load import infer_primary_from_secondary

PRIMARY_TO_PROFILE = {
    "玄幻": "xuanhuan",
    "诸天无限": "xuanhuan",
    "仙侠": "xianxia",
    "悬疑灵异": "suspense",
    "悬疑侦探女频": "suspense",
}


def _normalize_profiles(names: list[str]) -> list[str]:
    result: list[str] = []
    for name in names:
        if name and name not in result:
            result.append(name)
    if "common" not in result:
        result.insert(0, "common")
    return result


def resolve_profile_names(meta: dict, explicit_profiles: list[str] | None = None) -> list[str]:
    """Resolve ordered profile names from meta.yaml-like data."""
    if explicit_profiles:
        return _normalize_profiles(explicit_profiles)

    profiles = ["common"]
    genres = meta.get("genre") or meta.get("genre_primary") or []
    if isinstance(genres, str):
        genres = [genres]

    for genre in genres:
        profile = PRIMARY_TO_PROFILE.get(genre)
        if profile:
            profiles.append(profile)

        inferred = infer_primary_from_secondary(genre)
        inferred_profile = PRIMARY_TO_PROFILE.get(inferred)
        if inferred_profile:
            profiles.append(inferred_profile)

    return _normalize_profiles(profiles)
