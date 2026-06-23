from pathlib import Path

import yaml

from novel_material.audit.models import AuditSeverity
from novel_material.audit.rules import (
    AuditContext,
    check_insight_coverage,
    run_deterministic_rules,
)


def write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True),
        encoding="utf-8",
    )


def write_core_files(
    novel: Path,
    *,
    status: str = "analyzed",
    chapter_index: list[dict] | None = None,
) -> None:
    index = chapter_index or [{"chapter": 1, "type": "normal"}]
    write_yaml(
        novel / "meta.yaml",
        {"material_id": "nm_demo", "status": status},
    )
    write_yaml(novel / "chapter_index.yaml", index)
    write_yaml(
        novel / "chapters.yaml",
        [{"chapter": item["chapter"]} for item in index],
    )


def test_missing_core_fact_files_are_blockers(tmp_path: Path) -> None:
    issues = run_deterministic_rules(AuditContext("nm_demo", tmp_path / "nm_demo"))

    assert {item.code for item in issues} == {
        "meta_missing",
        "chapter_index_missing",
        "chapters_missing",
    }
    assert {item.severity for item in issues} == {AuditSeverity.BLOCKER}


def test_chapter_coverage_reports_bounded_missing_chapter_evidence(
    tmp_path: Path,
) -> None:
    novel = tmp_path / "nm_demo"
    write_yaml(novel / "meta.yaml", {"material_id": "nm_demo"})
    write_yaml(
        novel / "chapter_index.yaml",
        [{"chapter": chapter} for chapter in range(1, 62)],
    )
    write_yaml(novel / "chapters.yaml", [{"chapter": 1}])

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))

    issue = next(item for item in issues if item.code == "chapter_coverage_incomplete")
    assert issue.code == "chapter_coverage_incomplete"
    assert issue.severity is AuditSeverity.BLOCKER
    assert issue.artifact == "chapters.yaml"
    assert issue.evidence == {
        "expected": 61,
        "actual": 1,
        "missing_chapters": list(range(2, 52)),
        "missing_count": 60,
    }


def test_major_character_statistical_fallback_is_error(tmp_path: Path) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel)
    write_yaml(
        novel / "characters/profiles/主角.yaml",
        {
            "name": "主角",
            "role": "protagonist",
            "description": "出场 100 章，为主要角色之一。",
            "arc_summary": None,
            "psychology": {},
            "relationships": [],
        },
    )

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))

    fallback = next(item for item in issues if item.code == "character_profile_fallback")
    assert fallback.severity is AuditSeverity.ERROR
    assert fallback.evidence["missing_fields"] == [
        "arc_summary",
        "psychology",
        "relationships",
    ]


def test_supporting_fallback_is_warning_and_minor_profile_is_ignored(
    tmp_path: Path,
) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel)
    write_yaml(
        novel / "characters/profiles/配角.yaml",
        {"name": "配角", "role": "supporting", "description": "简档"},
    )
    write_yaml(
        novel / "characters/profiles/路人.yaml",
        {"name": "路人", "role": "minor", "description": "简档"},
    )

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))
    fallbacks = [item for item in issues if item.code == "character_profile_fallback"]

    assert len(fallbacks) == 1
    assert fallbacks[0].artifact.endswith("配角.yaml")
    assert fallbacks[0].severity is AuditSeverity.WARNING


def test_worldbuilding_empty_and_legacy_evidence_are_reported(
    tmp_path: Path,
) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel)
    write_yaml(
        novel / "worldbuilding/_index.yaml",
        {
            "llm_success": False,
            "power_system_levels": 0,
            "region_count": 0,
            "faction_count": 0,
            "lore_items": 0,
        },
    )

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))
    by_code = {item.code: item for item in issues}

    assert by_code["worldbuilding_empty"].severity is AuditSeverity.ERROR
    legacy = by_code["worldbuilding_legacy_without_evidence"]
    assert legacy.severity is AuditSeverity.WARNING
    assert legacy.reviewable is True


def test_zero_power_levels_alone_does_not_mark_worldbuilding_empty(
    tmp_path: Path,
) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel)
    write_yaml(
        novel / "worldbuilding/_index.yaml",
        {
            "llm_success": True,
            "power_system_levels": 0,
            "region_count": 2,
            "faction_count": 1,
            "lore_items": 0,
        },
    )

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))

    assert "worldbuilding_empty" not in {item.code for item in issues}


def test_finalized_material_reports_each_missing_stage_entry_file(
    tmp_path: Path,
) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel, status="finalized")

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))
    missing = [item for item in issues if item.code == "finalized_artifact_missing"]

    assert {item.artifact for item in missing} == {
        "outline/_index.yaml",
        "characters/_index.yaml",
        "worldbuilding/_index.yaml",
        "tags.yaml",
    }
    assert {item.severity for item in missing} == {AuditSeverity.ERROR}


def test_non_finalized_material_does_not_require_stage_entry_files(
    tmp_path: Path,
) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel, status="analyzed")

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))

    assert "finalized_artifact_missing" not in {item.code for item in issues}


def test_missing_insights_directory_is_information_only(tmp_path: Path) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel)

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))

    issue = next(item for item in issues if item.code == "insights_missing")
    assert issue.severity is AuditSeverity.INFO


def test_insight_coverage_excludes_special_chapters_and_reports_placeholders(
    tmp_path: Path,
) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(
        novel,
        chapter_index=[
            {"chapter": 1, "type": "normal"},
            {"chapter": 2, "type": "afterword"},
            {"chapter": 3, "type": "extra"},
        ],
    )
    write_yaml(
        novel / "chapter_insights/0001.yaml",
        {
            "chapter": 1,
            "quality": {"validation_errors": ["批次未返回本章结果"]},
        },
    )
    write_yaml(
        novel / "chapter_insights/0002.yaml",
        {"chapter": 2, "quality": {"validation_errors": []}},
    )

    issues = run_deterministic_rules(AuditContext("nm_demo", novel))
    by_code = {item.code: item for item in issues}

    incomplete = by_code["insight_coverage_incomplete"]
    assert incomplete.severity is AuditSeverity.WARNING
    assert incomplete.evidence == {
        "expected": 2,
        "processed": 1,
        "missing_chapters": [3],
        "missing_count": 1,
    }
    placeholder = by_code["insight_failed_placeholder"]
    assert placeholder.severity is AuditSeverity.WARNING
    assert placeholder.evidence == {
        "failed_chapters": [1],
        "failed_count": 1,
    }


def test_numeric_insight_files_do_not_require_yaml_parsing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    write_core_files(novel)
    write_yaml(
        novel / "chapter_insights/0001.yaml",
        {"chapter": 1, "quality": {"validation_errors": []}},
    )
    monkeypatch.setattr(
        "novel_material.audit.rules.load_yaml",
        lambda _path: (_ for _ in ()).throw(AssertionError("不应解析数字 insight")),
    )

    assert tuple(check_insight_coverage(AuditContext("nm_demo", novel))) == ()
