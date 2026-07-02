"""现有小说产物的确定性只读审计规则。"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from novel_material.infra.common import is_special_chapter_type
from novel_material.infra.yaml_io import load_yaml, load_yaml_list
from novel_material.worldbuilding.reader import load_worldbuilding_view

from .models import ArtifactIssue, AuditSeverity, ReviewState


@dataclass(frozen=True)
class AuditContext:
    """一次素材审计所需的只读路径上下文。"""

    material_id: str
    novel_dir: Path


AuditRule = Callable[[AuditContext], Iterable[ArtifactIssue]]


def _issue(
    code: str,
    severity: AuditSeverity,
    artifact: str,
    message: str,
    *,
    evidence: dict | None = None,
    next_actions: tuple[str, ...] = (),
    reviewable: bool = False,
) -> ArtifactIssue:
    """构造具有统一复审初始状态的问题条目。"""
    return ArtifactIssue(
        code=code,
        severity=severity,
        artifact=artifact,
        message=message,
        evidence=evidence or {},
        next_actions=next_actions,
        reviewable=reviewable,
        review_state=(ReviewState.PENDING if reviewable else ReviewState.NOT_REQUIRED),
    )


def check_required_files(context: AuditContext) -> Iterable[ArtifactIssue]:
    """检查后续审计所依赖的三份核心事实文件。"""
    required_files = (
        ("meta.yaml", "meta_missing"),
        ("chapter_index.yaml", "chapter_index_missing"),
        ("chapters.yaml", "chapters_missing"),
    )
    for filename, code in required_files:
        if not (context.novel_dir / filename).is_file():
            yield _issue(
                code,
                AuditSeverity.BLOCKER,
                filename,
                f"缺少核心事实文件 {filename}",
                next_actions=(f"nm pipeline continue {context.material_id}",),
            )


def _chapter_numbers(entries: list) -> set[int]:
    """从 YAML 列表中提取合法章节号，忽略无效条目。"""
    return {
        chapter
        for entry in entries
        if isinstance(entry, dict)
        and isinstance((chapter := entry.get("chapter")), int)
        and not isinstance(chapter, bool)
    }


def check_chapter_coverage(context: AuditContext) -> Iterable[ArtifactIssue]:
    """比较章节索引和分析快照，报告尚未分析的章节。"""
    index_path = context.novel_dir / "chapter_index.yaml"
    chapters_path = context.novel_dir / "chapters.yaml"
    if not index_path.is_file() or not chapters_path.is_file():
        return

    expected = _chapter_numbers(load_yaml_list(index_path))
    actual = _chapter_numbers(load_yaml_list(chapters_path))
    missing = sorted(expected - actual)
    if not missing:
        return

    yield _issue(
        "chapter_coverage_incomplete",
        AuditSeverity.BLOCKER,
        "chapters.yaml",
        "章节分析覆盖不完整",
        evidence={
            "expected": len(expected),
            "actual": len(actual),
            "missing_chapters": missing[:50],
            "missing_count": len(missing),
        },
        next_actions=(f"nm pipeline continue {context.material_id}",),
    )


_STATISTICAL_PROFILE_RE = re.compile(r"^出场\s+\d+\s+章，为主要角色之一。?$")
_FULL_PROFILE_FIELDS = ("arc_summary", "psychology", "relationships")


def check_character_profiles(context: AuditContext) -> Iterable[ArtifactIssue]:
    """识别主要人物和配角的统计兜底或空壳档案。"""
    profiles_dir = context.novel_dir / "characters" / "profiles"
    if not profiles_dir.is_dir():
        return

    profiles_by_name: dict[str, dict] = {}
    for profile_path in sorted(profiles_dir.glob("*.yaml")):
        profile = load_yaml(profile_path)
        name = profile.get("name")
        if isinstance(name, str) and name:
            profiles_by_name[name] = profile
        role = profile.get("role")
        profile_level = profile.get("profile_level")
        if profile_level == "brief":
            if not _brief_profile_has_minimum_info(profile):
                yield _issue(
                    "character_profile_fallback",
                    AuditSeverity.WARNING,
                    profile_path.relative_to(context.novel_dir).as_posix(),
                    "人物简档缺少基础可用信息",
                    evidence={"profile_level": "brief"},
                    next_actions=(f"nm pipeline characters {context.material_id}",),
                )
            continue

        if profile_level in {"fallback", "partial", "enriched"}:
            schema_issues = profile.get("schema_issues")
            if not isinstance(schema_issues, list):
                schema_issues = []
            if profile_level == "fallback":
                severity = (
                    AuditSeverity.ERROR
                    if role in {"protagonist", "antagonist"}
                    else AuditSeverity.WARNING
                )
                code = "character_profile_fallback"
                message = "人物档案仍是统计兜底或缺少完整小传字段"
            elif profile_level == "partial":
                severity = AuditSeverity.WARNING
                code = "character_profile_partial"
                message = "人物档案为 partial，需按 schema_issues 定向修复"
            elif schema_issues:
                severity = AuditSeverity.INFO
                code = "character_profile_partial"
                message = "人物档案为 enriched，但仍有低风险 schema_issues"
            else:
                continue
            yield _issue(
                code,
                severity,
                profile_path.relative_to(context.novel_dir).as_posix(),
                message,
                evidence={
                    "profile_level": profile_level,
                    "schema_issues": schema_issues,
                },
                next_actions=(f"nm pipeline characters {context.material_id}",),
            )
            continue

        requires_full_profile = role in {"protagonist", "antagonist"} or (
            profile_level == "full"
        )
        if not requires_full_profile and role != "supporting":
            continue

        missing_fields = [
            field for field in _FULL_PROFILE_FIELDS if not profile.get(field)
        ]
        biography_complete = profile.get("biography_complete")
        if profile_level == "full" and biography_complete is not True:
            missing_fields.append("biography_complete")
        description = profile.get("description")
        statistical_description = (
            isinstance(description, str)
            and _STATISTICAL_PROFILE_RE.fullmatch(description.strip()) is not None
        )
        if not missing_fields and not statistical_description:
            continue

        evidence: dict[str, object] = {"missing_fields": missing_fields}
        if statistical_description:
            evidence["statistical_description"] = True
        if profile_level:
            evidence["profile_level"] = profile_level
        if profile_level == "full":
            evidence["biography_complete"] = biography_complete is True
        yield _issue(
            "character_profile_fallback",
            (
                AuditSeverity.ERROR
                if requires_full_profile
                else AuditSeverity.WARNING
            ),
            profile_path.relative_to(context.novel_dir).as_posix(),
            "人物档案仍是统计兜底或缺少完整小传字段",
            evidence=evidence,
            next_actions=(f"nm pipeline characters {context.material_id}",),
        )

    index = load_yaml(context.novel_dir / "characters" / "_index.yaml")
    targets = index.get("biography_targets")
    if isinstance(targets, list) and targets:
        target_names = [
            item.get("name")
            for item in targets
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        missing_targets = [
            name
            for name in target_names
            if not _profile_has_completed_biography(profiles_by_name.get(name))
        ]
        if missing_targets:
            yield _issue(
                "character_biography_incomplete",
                AuditSeverity.ERROR,
                "characters/_index.yaml",
                "完整小传目标未全部完成",
                evidence={
                    "target_count": len(target_names),
                    "completed_count": len(target_names) - len(missing_targets),
                    "missing_targets": missing_targets,
                    "biography_target_count": index.get("biography_target_count"),
                    "biography_completed_count": index.get(
                        "biography_completed_count"
                    ),
                    "biography_failed_count": index.get("biography_failed_count"),
                },
                next_actions=(f"nm pipeline characters {context.material_id}",),
            )


def _brief_profile_has_minimum_info(profile: dict) -> bool:
    """简档只要求具备至少一项可用基础信息。"""
    return any(
        profile.get(field)
        for field in (
            "name",
            "role",
            "description",
            "first_appearance_chapter",
            "narrative_function",
        )
    )


def _profile_has_completed_biography(profile: dict | None) -> bool:
    if not profile:
        return False
    return (
        profile.get("profile_level") == "full"
        and profile.get("biography_complete") is True
    )


def check_worldbuilding(context: AuditContext) -> Iterable[ArtifactIssue]:
    """检查世界观索引中的空结构、证据能力缺口和 layered 引用完整性。"""
    index_path = context.novel_dir / "worldbuilding" / "_index.yaml"
    if not index_path.is_file():
        return

    index = load_yaml(index_path)
    if index.get("layout") == "layered":
        yield from _check_layered_worldbuilding(context)
        return

    count_fields = (
        "power_system_levels",
        "region_count",
        "faction_count",
        "lore_items",
    )
    if not index.get("llm_success") and all(not index.get(field) for field in count_fields):
        yield _issue(
            "worldbuilding_empty",
            AuditSeverity.ERROR,
            "worldbuilding/_index.yaml",
            "世界观提取失败且四类结构均为空",
            evidence={field: index.get(field, 0) for field in count_fields},
            next_actions=(f"nm pipeline worldbuilding {context.material_id}",),
        )

    evidence_fields = {
        "dimension_count",
        "entity_count",
        "relationship_count",
        "evidence_count",
    }
    if any(field in index for field in count_fields) and not any(
        field in index for field in evidence_fields
    ):
        yield _issue(
            "worldbuilding_legacy_without_evidence",
            AuditSeverity.WARNING,
            "worldbuilding/_index.yaml",
            "旧版世界观结构不包含实体关系与章节证据统计",
            evidence={"legacy_fields": list(count_fields)},
            reviewable=True,
        )


def _check_layered_worldbuilding(context: AuditContext) -> Iterable[ArtifactIssue]:
    view = load_worldbuilding_view(context.novel_dir)
    applicable_dimensions = [
        item.id for item in view.dimensions if item.applicability == "applicable"
    ]
    has_driving_mechanisms = bool(
        view.overview is not None and view.overview.driving_mechanisms
    )
    dimension_status = view.index.dimension_status
    if (
        applicable_dimensions
        and not view.index.llm_success
        and not view.entities
        and not has_driving_mechanisms
        and all(dimension_status.get(item) == "missing" for item in applicable_dimensions)
    ):
        yield _issue(
            "worldbuilding_empty",
            AuditSeverity.ERROR,
            "worldbuilding/_index.yaml",
            "世界观提取失败且所有适用维度均缺失",
            evidence={
                "applicable_dimensions": applicable_dimensions,
                "dimension_status": dimension_status,
                "entity_count": len(view.entities),
                "has_driving_mechanisms": has_driving_mechanisms,
            },
            next_actions=(f"nm pipeline worldbuilding {context.material_id}",),
        )
        return

    if applicable_dimensions and not view.entities and not has_driving_mechanisms:
        yield _issue(
            "worldbuilding_empty_applicable_dimension",
            AuditSeverity.WARNING,
            "worldbuilding/dimensions.yaml",
            "世界观存在适用维度，但缺少实体或运行机制支撑",
            evidence={
                "applicable_dimensions": applicable_dimensions,
                "entity_count": len(view.entities),
                "has_driving_mechanisms": has_driving_mechanisms,
            },
            next_actions=(f"nm pipeline worldbuilding {context.material_id}",),
        )

    for entity in view.entities:
        if entity.importance != "primary" or entity.evidence:
            continue
        yield _issue(
            "worldbuilding_entity_missing_evidence",
            AuditSeverity.WARNING,
            f"worldbuilding/entities/{entity.id}.yaml",
            "主要世界观实体缺少章节证据",
            evidence={
                "entity_id": entity.id,
                "name": entity.name,
                "type": entity.type,
            },
            next_actions=(f"nm pipeline worldbuilding {context.material_id}",),
        )

    entity_ids = {item.id for item in view.entities}
    for relation in view.relations:
        unknown_ids = [
            entity_id
            for entity_id in (relation.source_id, relation.target_id)
            if entity_id not in entity_ids
        ]
        if not unknown_ids:
            continue
        yield _issue(
            "worldbuilding_relation_unknown_entity",
            AuditSeverity.ERROR,
            "worldbuilding/relations.yaml",
            "世界观关系引用了不存在的实体",
            evidence={
                "relation_id": relation.id,
                "source_id": relation.source_id,
                "target_id": relation.target_id,
                "unknown_entity_ids": unknown_ids,
            },
            next_actions=(f"nm pipeline worldbuilding {context.material_id}",),
        )


def check_finalized_artifacts(context: AuditContext) -> Iterable[ArtifactIssue]:
    """finalized 素材必须保留四个专题阶段的入口文件。"""
    meta_path = context.novel_dir / "meta.yaml"
    if not meta_path.is_file() or load_yaml(meta_path).get("status") != "finalized":
        return

    entry_files = (
        "outline/_index.yaml",
        "characters/_index.yaml",
        "worldbuilding/_index.yaml",
        "tags.yaml",
    )
    for artifact in entry_files:
        if not (context.novel_dir / artifact).is_file():
            yield _issue(
                "finalized_artifact_missing",
                AuditSeverity.ERROR,
                artifact,
                "finalized 素材缺少专题分析入口文件",
                evidence={"status": "finalized"},
                next_actions=(f"nm pipeline continue {context.material_id}",),
            )


def _expected_insight_chapters(index: list) -> set[int]:
    """返回应生成 insight 的正文与番外章节号。"""
    return {
        chapter
        for item in index
        if isinstance(item, dict)
        and not is_special_chapter_type(str(item.get("type", "normal")))
        and isinstance((chapter := item.get("chapter")), int)
        and not isinstance(chapter, bool)
    }


_VALIDATION_ERRORS_RE = re.compile(r"(?m)^\s*validation_errors:")
_EMPTY_VALIDATION_ERRORS_RE = re.compile(
    r"(?m)^\s*validation_errors:\s*\[\s*\]\s*(?:#.*)?$"
)


def _insight_file_state(path: Path) -> tuple[int | None, bool]:
    """用稳定文件名和轻量标记读取章节号及失败占位状态。"""
    if path.stem.isdigit():
        content = path.read_text(encoding="utf-8")
        has_validation_errors = _VALIDATION_ERRORS_RE.search(content) is not None
        validation_errors_empty = (
            _EMPTY_VALIDATION_ERRORS_RE.search(content) is not None
        )
        return int(path.stem), has_validation_errors and not validation_errors_empty

    insight = load_yaml(path)
    chapter = insight.get("chapter")
    if not isinstance(chapter, int) or isinstance(chapter, bool):
        chapter = None
    quality = insight.get("quality")
    failed = isinstance(quality, dict) and bool(quality.get("validation_errors"))
    return chapter, failed


def check_insight_coverage(context: AuditContext) -> Iterable[ArtifactIssue]:
    """检查 insight 文件覆盖率，并单列已落盘的失败占位。"""
    index_path = context.novel_dir / "chapter_index.yaml"
    if not index_path.is_file():
        return

    insights_dir = context.novel_dir / "chapter_insights"
    if not insights_dir.is_dir():
        yield _issue(
            "insights_missing",
            AuditSeverity.INFO,
            "chapter_insights",
            "尚未生成章节深度分析目录",
            next_actions=(f"nm pipeline insights {context.material_id}",),
        )
        return

    expected = _expected_insight_chapters(
        load_yaml_list(index_path)
    )
    present: set[int] = set()
    failed: set[int] = set()
    for path in sorted(insights_dir.glob("*.yaml")):
        chapter, is_failed = _insight_file_state(path)
        if chapter is None or chapter not in expected:
            continue
        present.add(chapter)
        if is_failed:
            failed.add(chapter)

    missing = sorted(expected - present)
    if missing:
        yield _issue(
            "insight_coverage_incomplete",
            AuditSeverity.WARNING,
            "chapter_insights",
            "章节深度分析覆盖不完整",
            evidence={
                "expected": len(expected),
                "processed": len(present),
                "missing_chapters": missing[:50],
                "missing_count": len(missing),
            },
            next_actions=(f"nm pipeline insights {context.material_id}",),
        )

    if failed:
        failed_chapters = sorted(failed)
        yield _issue(
            "insight_failed_placeholder",
            AuditSeverity.WARNING,
            "chapter_insights",
            "部分 insight 文件记录了生成或校验失败",
            evidence={
                "failed_chapters": failed_chapters[:50],
                "failed_count": len(failed_chapters),
            },
            next_actions=(f"nm pipeline insights {context.material_id}",),
        )


RULES: tuple[tuple[str, AuditRule], ...] = (
    ("required_files", check_required_files),
    ("chapter_coverage", check_chapter_coverage),
    ("characters", check_character_profiles),
    ("worldbuilding", check_worldbuilding),
    ("finalized_artifacts", check_finalized_artifacts),
    ("insight_coverage", check_insight_coverage),
)


def run_deterministic_rules(context: AuditContext) -> tuple[ArtifactIssue, ...]:
    """依注册顺序运行规则，并稳定排序返回问题。"""
    issues = [item for _name, rule in RULES for item in rule(context)]
    return tuple(
        sorted(
            issues,
            key=lambda item: (item.severity.value, item.code, item.artifact),
        )
    )


__all__ = [
    "AuditContext",
    "AuditRule",
    "RULES",
    "check_chapter_coverage",
    "check_character_profiles",
    "check_finalized_artifacts",
    "check_insight_coverage",
    "check_required_files",
    "check_worldbuilding",
    "run_deterministic_rules",
]
