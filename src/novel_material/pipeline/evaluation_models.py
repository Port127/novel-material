"""前置全局导航 evaluation.yaml 的模型与兼容读取。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from novel_material.infra.yaml_io import load_yaml


_LEGACY_STAGE_NAMES = (
    "opening",
    "development",
    "turning",
    "climax",
    "resolution",
)


class TurningPoint(BaseModel):
    """采样推断出的阶段转折点。"""

    model_config = ConfigDict(frozen=True)

    chapter: int = Field(ge=1)
    event: str = Field(min_length=1)


class StageMapItem(BaseModel):
    """前置导航中的故事阶段地图。"""

    model_config = ConfigDict(frozen=True)

    stage: str = Field(min_length=1)
    chapter_ranges: tuple[tuple[int, int], ...] = ()
    central_conflict: str = ""
    turning_points: tuple[TurningPoint, ...] = ()

    @model_validator(mode="after")
    def validate_ranges(self) -> "StageMapItem":
        for start, end in self.chapter_ranges:
            if start < 1 or end < start:
                raise ValueError("chapter_ranges 必须是正向章节范围")
        return self


class CoreCharacterCandidate(BaseModel):
    """前置导航推断出的核心人物候选。"""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    reasons: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)


class SampleCoverage(BaseModel):
    """前置导航采样覆盖范围。"""

    model_config = ConfigDict(frozen=True)

    sampled_chapters: tuple[int, ...] = ()
    covered_ranges: tuple[tuple[int, int], ...] = ()
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_ranges(self) -> "SampleCoverage":
        for chapter in self.sampled_chapters:
            if chapter < 1:
                raise ValueError("sampled_chapters 必须为正整数")
        for start, end in self.covered_ranges:
            if start < 1 or end < start:
                raise ValueError("covered_ranges 必须是正向章节范围")
        return self


class EvaluationNavigation(BaseModel):
    """evaluation.yaml 3.0.0 的只读导航视图。"""

    model_config = ConfigDict(frozen=True)

    schema_version: Literal["3.0.0"] = "3.0.0"
    source_schema_version: str = "3.0.0"
    novel_type: tuple[str, ...] = ()
    premise: str = ""
    main_thread_summary: str = ""
    stage_map: tuple[StageMapItem, ...] = ()
    core_character_candidates: tuple[CoreCharacterCandidate, ...] = ()
    worldbuilding_dimensions: tuple[str, ...] = ()
    analysis_focus: tuple[str, ...] = ()
    sample_coverage: SampleCoverage = Field(default_factory=SampleCoverage)
    evaluation_timestamp: str | None = None


def normalize_evaluation_navigation(payload: object) -> EvaluationNavigation:
    """把新旧 evaluation payload 规范化为 3.0.0 导航视图。"""
    if not isinstance(payload, dict):
        raise TypeError("evaluation payload 必须是对象")

    schema_version = str(payload.get("schema_version", ""))
    if schema_version == "3.0.0":
        return EvaluationNavigation.model_validate(payload)

    if schema_version == "2.0.1" or _looks_like_legacy_evaluation(payload):
        return _adapt_legacy_evaluation(payload)

    raise ValueError(f"不支持的 evaluation schema_version: {schema_version or 'missing'}")


def load_evaluation_navigation(novel_dir: Path) -> EvaluationNavigation | None:
    """从素材目录只读加载 evaluation.yaml，并返回 3.0.0 导航视图。"""
    evaluation_path = novel_dir / "evaluation.yaml"
    if not evaluation_path.exists():
        return None
    return normalize_evaluation_navigation(load_yaml(evaluation_path))


def _looks_like_legacy_evaluation(payload: dict[str, Any]) -> bool:
    return "stage_summaries" in payload or "core_characters_hint" in payload


def _adapt_legacy_evaluation(payload: dict[str, Any]) -> EvaluationNavigation:
    stage_summaries = payload.get("stage_summaries", {})
    stage_map: list[dict[str, object]] = []
    for index, name in enumerate(_LEGACY_STAGE_NAMES, start=1):
        summary = _legacy_stage_summary(stage_summaries, index)
        stage_map.append(
            {
                "stage": name,
                "chapter_ranges": (),
                "central_conflict": summary,
                "turning_points": (),
            }
        )

    candidates = [
        {
            "name": name,
            "reasons": ("legacy_core_characters_hint",),
            "confidence": 0.5,
        }
        for name in payload.get("core_characters_hint", ())
        if isinstance(name, str) and name.strip()
    ]

    return EvaluationNavigation(
        source_schema_version=str(payload.get("schema_version", "2.0.1")),
        novel_type=tuple(_string_items(payload.get("novel_type", ()))),
        premise="",
        main_thread_summary=str(payload.get("main_thread_summary", "") or ""),
        stage_map=tuple(StageMapItem.model_validate(item) for item in stage_map),
        core_character_candidates=tuple(
            CoreCharacterCandidate.model_validate(item) for item in candidates
        ),
        sample_coverage=SampleCoverage(
            limitations=("legacy_evaluation_without_sample_coverage",)
        ),
        evaluation_timestamp=payload.get("evaluation_timestamp"),
    )


def _legacy_stage_summary(stage_summaries: object, index: int) -> str:
    if not isinstance(stage_summaries, dict):
        return ""
    value = stage_summaries.get(index, stage_summaries.get(str(index), ""))
    return str(value or "")


def _string_items(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


__all__ = [
    "CoreCharacterCandidate",
    "EvaluationNavigation",
    "SampleCoverage",
    "StageMapItem",
    "TurningPoint",
    "load_evaluation_navigation",
    "normalize_evaluation_navigation",
]
