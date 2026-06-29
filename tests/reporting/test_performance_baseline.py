from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

import yaml

from novel_material.audit import audit_material
from novel_material.reporting import ReportWriter, build_run_report, render_markdown
from novel_material.runtime.contracts import RunStatus
from novel_material.runtime.testing import event


def write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True),
        encoding="utf-8",
    )


def write_large_rules_only_fixture(novel_dir: Path) -> None:
    chapter_index = [
        {"chapter": chapter, "title": f"第 {chapter} 章", "type": "normal"}
        for chapter in range(1, 1085)
    ]
    write_yaml(
        novel_dir / "meta.yaml",
        {"material_id": "nm_perf", "status": "analyzed"},
    )
    write_yaml(novel_dir / "chapter_index.yaml", chapter_index)
    write_yaml(
        novel_dir / "chapters.yaml",
        [{"chapter": item["chapter"], "summary": "已分析"} for item in chapter_index],
    )
    write_yaml(
        novel_dir / "worldbuilding/_index.yaml",
        {
            "llm_success": True,
            "dimension_count": 3,
            "entity_count": 12,
            "relationship_count": 8,
            "evidence_count": 42,
        },
    )
    for index in range(1, 135):
        role = "protagonist" if index == 1 else "supporting"
        write_yaml(
            novel_dir / f"characters/profiles/角色{index:03d}.yaml",
            {
                "name": f"角色{index:03d}",
                "role": role,
                "description": "完整人物档案",
                "arc_summary": "成长轨迹清晰",
                "psychology": {"motivation": "追求目标"},
                "relationships": [{"name": "同伴", "relation": "盟友"}],
            },
        )


def run_report_events(audit_payload: dict) -> list:
    started = datetime(2026, 6, 23, 1, 0, tzinfo=timezone.utc)
    return [
        event(
            "RunStarted",
            run_id="run-perf",
            occurred_at=started,
            material_id="nm_perf",
            command="validate artifacts",
        ),
        event(
            "StageCompleted",
            run_id="run-perf",
            occurred_at=started + timedelta(milliseconds=500),
            stage_id="stage-audit",
            material_id="nm_perf",
            command="validate artifacts",
            status=RunStatus.SUCCESS,
            duration_ms=500,
            attributes={
                "stage_name": "audit",
                "counts": {"expected": 1084, "processed": 1084},
                "diagnostics": [],
            },
        ),
        event(
            "ArtifactAuditCompleted",
            run_id="run-perf",
            occurred_at=started + timedelta(milliseconds=500),
            stage_id="stage-audit",
            material_id="nm_perf",
            command="validate artifacts",
            status=RunStatus.SUCCESS,
            attributes={"audit": audit_payload},
        ),
        event(
            "RunCompleted",
            run_id="run-perf",
            occurred_at=started + timedelta(seconds=1),
            material_id="nm_perf",
            command="validate artifacts",
            status=RunStatus.SUCCESS,
            attributes={"counts": {}, "diagnostics": []},
        ),
    ]


def test_rules_only_audit_and_report_generation_perf_baseline(
    tmp_path: Path,
    record_property,
) -> None:
    novel_dir = tmp_path / "nm_perf"
    write_large_rules_only_fixture(novel_dir)

    started = perf_counter()
    audit = audit_material("nm_perf", novels_dir=tmp_path)
    report = build_run_report(run_report_events(audit.model_dump(mode="json")))
    markdown = render_markdown(report)
    ReportWriter(novel_dir).write(report)
    elapsed_seconds = perf_counter() - started

    record_property("baseline_type", audit.review_budget.mode)
    record_property("rules_only_perf_seconds", elapsed_seconds)

    assert audit.review_budget.mode == "rules_only"
    assert audit.review_budget.calls_used == 0
    assert report.artifact_quality.review_budget.mode == "rules_only"
    assert "运行与产物质量报告" in markdown
    assert (novel_dir / "reports" / "latest.yaml").is_file()
    assert elapsed_seconds < 2.0
