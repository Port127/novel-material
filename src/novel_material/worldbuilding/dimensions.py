"""题材自适应世界观维度路由。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import WorldbuildingDimension


GENRE_PROFILE_ALIASES = {
    "都市": "urban",
    "现实": "urban",
    "重生": "urban",
    "玄幻": "xuanhuan",
    "仙侠": "xianxia",
    "悬疑": "suspense",
    "悬疑灵异": "suspense",
    "悬疑侦探女频": "suspense",
}

POWER_KEYWORDS = ("修炼", "境界", "灵气", "法力", "功法", "宗门")

PROFILE_DIMENSIONS = {
    "common": (
        ("organization_network", "组织网络", "social", "通用世界观需要识别组织与群体网络"),
        ("locations", "地点空间", "space", "通用世界观需要识别关键地点和空间结构"),
        ("rules", "制度规则", "rule", "通用世界观需要识别约束角色行动的规则"),
        ("history_background", "历史背景", "history", "通用世界观需要识别影响当前剧情的背景"),
        ("core_concepts", "核心概念", "concept", "通用世界观需要识别反复出现的概念"),
    ),
    "urban": (
        ("era_context", "时代环境", "social", "都市题材通常受时代与现实环境约束"),
        ("business_rules", "商业规则", "social", "都市/重生题材常以商业和资源竞争推动剧情"),
        ("social_classes", "社会阶层", "social", "都市题材常通过阶层差异制造压力"),
        ("legal_system", "法律制度", "rule", "现实向题材需要识别法律和制度边界"),
        ("campus_workplace_network", "校园/职场网络", "social", "都市题材常依赖校园或职场组织关系"),
    ),
    "xuanhuan": (
        ("cultivation_levels", "力量体系", "power", "玄幻题材通常需要识别力量等级"),
        ("resources", "资源体系", "resource", "玄幻题材常由资源争夺驱动剧情"),
        ("factions", "势力结构", "social", "玄幻题材需要识别宗门、家族或组织"),
        ("geography_hierarchy", "地理层级", "space", "玄幻题材常有地域层级和空间规则"),
        ("taboos", "禁忌规则", "rule", "玄幻题材常存在禁忌和超自然约束"),
    ),
    "xianxia": (
        ("cultivation_levels", "修炼体系", "power", "仙侠题材通常需要识别修炼体系"),
        ("sect_structure", "宗门结构", "social", "仙侠题材常由宗门关系组织角色"),
        ("resources", "资源体系", "resource", "仙侠题材常围绕灵物、功法和机缘展开"),
        ("geography_hierarchy", "地域层级", "space", "仙侠题材常有洞天、宗门和地域层级"),
        ("cosmic_rules", "因果/天道规则", "rule", "仙侠题材常存在天道、因果或誓约约束"),
    ),
    "suspense": (
        ("spatial_structure", "空间结构", "space", "悬疑题材需要识别封闭空间或案发地点"),
        ("institutional_context", "制度环境", "rule", "悬疑题材需要识别办案和社会制度"),
        ("secret_organizations", "秘密组织", "social", "悬疑题材可能存在隐秘群体"),
        ("information_rules", "信息规则", "rule", "悬疑题材由信息差、线索和隐瞒推动"),
        ("case_background", "案件背景", "history", "悬疑题材需要识别案件前史"),
    ),
}


@dataclass(frozen=True)
class DimensionRoutingResult:
    """世界观维度路由结果。"""

    source: dict[str, object]
    dimensions: tuple[WorldbuildingDimension, ...]


def resolve_worldbuilding_dimensions(
    *,
    meta: dict,
    navigation_dimensions: Iterable[str] = (),
    chapter_signals: dict | None = None,
) -> DimensionRoutingResult:
    """根据题材、前置导航和章级信号生成世界观维度。"""
    navigation = tuple(str(item) for item in navigation_dimensions if str(item))
    profiles = _resolve_profiles(meta, navigation)
    has_power_signal = _has_power_signal(navigation, chapter_signals or {})
    dimensions: dict[str, WorldbuildingDimension] = {}

    for profile in profiles:
        for dimension_id, name, category, reason in PROFILE_DIMENSIONS[profile]:
            _upsert_dimension(
                dimensions,
                WorldbuildingDimension(
                    id=dimension_id,
                    name=name,
                    category=category,
                    applicability="applicable",
                    reason=reason,
                    confidence=_confidence_for_profile(profile),
                ),
            )

    if "cultivation_levels" not in dimensions:
        applicability = "applicable" if has_power_signal else "not_applicable"
        reason = (
            "前置导航或章级信号提到修炼、境界、灵气等超自然力量"
            if has_power_signal
            else "章级事实和前置导航都未出现超自然力量体系"
        )
        dimensions["cultivation_levels"] = WorldbuildingDimension(
            id="cultivation_levels",
            name="修炼等级",
            category="power",
            applicability=applicability,
            reason=reason,
            confidence=0.78 if has_power_signal else 0.9,
        )
    elif has_power_signal:
        dimensions["cultivation_levels"] = dimensions[
            "cultivation_levels"
        ].model_copy(
            update={
                "applicability": "applicable",
                "reason": "前置导航或章级信号提到修炼、境界、灵气等超自然力量",
                "confidence": 0.82,
            }
        )

    return DimensionRoutingResult(
        source={
            "genre_profiles": profiles,
            "navigation_dimensions": navigation,
            "chapter_signal_keys": sorted((chapter_signals or {}).keys()),
        },
        dimensions=tuple(dimensions.values()),
    )


def _resolve_profiles(meta: dict, navigation: tuple[str, ...]) -> tuple[str, ...]:
    profiles = ["common"]
    genres = meta.get("genre") or meta.get("genre_primary") or []
    if isinstance(genres, str):
        genres = [genres]
    for genre in genres:
        profile = GENRE_PROFILE_ALIASES.get(str(genre))
        if profile and profile not in profiles:
            profiles.append(profile)
    joined_navigation = " ".join(navigation)
    if any(keyword in joined_navigation for keyword in ("商业", "校园", "职场")):
        _append_once(profiles, "urban")
    if any(keyword in joined_navigation for keyword in ("宗门", "修炼", "灵气", "境界")):
        _append_once(profiles, "xianxia")
    return tuple(profile for profile in profiles if profile in PROFILE_DIMENSIONS)


def _append_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _upsert_dimension(
    dimensions: dict[str, WorldbuildingDimension],
    dimension: WorldbuildingDimension,
) -> None:
    current = dimensions.get(dimension.id)
    if current is None or (
        current.applicability != "applicable"
        and dimension.applicability == "applicable"
    ):
        dimensions[dimension.id] = dimension


def _has_power_signal(navigation: tuple[str, ...], chapter_signals: dict) -> bool:
    texts = list(navigation)
    for value in chapter_signals.values():
        if isinstance(value, dict):
            texts.extend(str(key) for key in value.keys())
        elif isinstance(value, list):
            texts.extend(str(item) for item in value)
        else:
            texts.append(str(value))
    joined = " ".join(texts)
    return any(keyword in joined for keyword in POWER_KEYWORDS)


def _confidence_for_profile(profile: str) -> float:
    return 0.72 if profile == "common" else 0.82


__all__ = [
    "DimensionRoutingResult",
    "GENRE_PROFILE_ALIASES",
    "resolve_worldbuilding_dimensions",
]
