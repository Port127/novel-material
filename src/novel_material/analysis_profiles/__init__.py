"""Genre-aware analysis profile loading."""

from novel_material.analysis_profiles.loader import (
    AnalysisProfile,
    ProfileField,
    load_profile,
    load_profiles,
    merge_profiles,
)

__all__ = [
    "AnalysisProfile",
    "ProfileField",
    "load_profile",
    "load_profiles",
    "merge_profiles",
]
