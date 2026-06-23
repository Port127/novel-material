"""现有小说产物的确定性只读审计规则。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from novel_material.infra.yaml_io import load_yaml_list

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


RULES: tuple[tuple[str, AuditRule], ...] = (
    ("required_files", check_required_files),
    ("chapter_coverage", check_chapter_coverage),
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
    "check_required_files",
    "run_deterministic_rules",
]
