"""Load and merge genre-aware analysis profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from novel_material.infra.yaml_io import load_yaml

PROFILE_DIR = Path(__file__).parent / "profiles"


@dataclass(frozen=True)
class ProfileField:
    """A field required or supported by an analysis profile."""

    name: str
    description: str
    min_length: int | None = None
    max_length: int | None = None


@dataclass(frozen=True)
class AnalysisProfile:
    """A genre-aware analysis profile."""

    name: str
    display_name: str
    applies_to: list[str] = field(default_factory=list)
    required_fields: dict[str, ProfileField] = field(default_factory=dict)
    optional_fields: dict[str, ProfileField] = field(default_factory=dict)
    search_facets: list[str] = field(default_factory=list)
    quality_rules: list[str] = field(default_factory=list)
    prompt_additions: list[str] = field(default_factory=list)


def _parse_fields(raw: dict[str, Any] | None) -> dict[str, ProfileField]:
    fields: dict[str, ProfileField] = {}
    for name, data in (raw or {}).items():
        fields[name] = ProfileField(
            name=name,
            description=str(data.get("description", "")),
            min_length=data.get("min_length"),
            max_length=data.get("max_length"),
        )
    return fields


def load_profile(name: str) -> AnalysisProfile:
    """Load a single profile by file stem."""
    profile_path = PROFILE_DIR / f"{name}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"analysis profile not found: {profile_path}")

    data = load_yaml(profile_path)
    return AnalysisProfile(
        name=str(data["name"]),
        display_name=str(data.get("display_name", data["name"])),
        applies_to=list(data.get("applies_to", [])),
        required_fields=_parse_fields(data.get("required_fields")),
        optional_fields=_parse_fields(data.get("optional_fields")),
        search_facets=list(data.get("search_facets", [])),
        quality_rules=list(data.get("quality_rules", [])),
        prompt_additions=list(data.get("prompt_additions", [])),
    )


def load_profiles(names: list[str]) -> list[AnalysisProfile]:
    """Load profiles in the requested order."""
    return [load_profile(name) for name in names]


def merge_profiles(profiles: list[AnalysisProfile]) -> AnalysisProfile:
    """Merge profiles left-to-right; later profiles add genre-specific fields."""
    if not profiles:
        raise ValueError("at least one profile is required")

    required_fields: dict[str, ProfileField] = {}
    optional_fields: dict[str, ProfileField] = {}
    search_facets: list[str] = []
    quality_rules: list[str] = []
    prompt_additions: list[str] = []

    for profile in profiles:
        required_fields.update(profile.required_fields)
        optional_fields.update(profile.optional_fields)
        for facet in profile.search_facets:
            if facet not in search_facets:
                search_facets.append(facet)
        for rule in profile.quality_rules:
            if rule not in quality_rules:
                quality_rules.append(rule)
        prompt_additions.extend(profile.prompt_additions)

    return AnalysisProfile(
        name="+".join(p.name for p in profiles),
        display_name=" + ".join(p.display_name for p in profiles),
        applies_to=[item for p in profiles for item in p.applies_to],
        required_fields=required_fields,
        optional_fields=optional_fields,
        search_facets=search_facets,
        quality_rules=quality_rules,
        prompt_additions=prompt_additions,
    )
