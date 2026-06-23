from pathlib import Path

import yaml

from novel_material.audit.models import AuditSeverity
from novel_material.audit.rules import AuditContext, run_deterministic_rules


def write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True),
        encoding="utf-8",
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

    assert len(issues) == 1
    issue = issues[0]
    assert issue.code == "chapter_coverage_incomplete"
    assert issue.severity is AuditSeverity.BLOCKER
    assert issue.artifact == "chapters.yaml"
    assert issue.evidence == {
        "expected": 61,
        "actual": 1,
        "missing_chapters": list(range(2, 52)),
        "missing_count": 60,
    }
