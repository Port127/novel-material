from datetime import datetime, timezone

from novel_material.reporting.markdown import render_markdown
from novel_material.reporting.models import (
    BaselineComparison,
    PipelineRunReport,
    ReleaseGateReport,
)
from novel_material.runtime.contracts import RunStatus


def test_markdown_contains_conclusion_risks_and_next_actions(
    sample_report: PipelineRunReport,
) -> None:
    text = render_markdown(sample_report)

    assert "# 运行与产物质量报告" in text
    assert "状态：degraded" in text
    assert "API 调用：尝试 2，完成 1" in text
    assert "character_profile_fallback" in text
    assert "完整小传：目标 5，完成 4，失败 1，简档 3" in text
    assert "人物质量：full=2，enriched=1，partial=1，fallback=1，repair=1/2" in text
    assert "世界观：layered，实体 8，关系 6，证据 21，断裂关系 1，缺证实体 2" in text
    assert "nm pipeline characters" in text
    assert "未复审项" in text
    assert "[REDACTED]" in text
    assert "API Key" not in text
    assert "sk-secret-value" not in text


def test_markdown_sorts_issues_by_severity(
    sample_report: PipelineRunReport,
) -> None:
    text = render_markdown(sample_report)

    assert text.index("character_profile_fallback") < text.index(
        "budget_review_pending"
    )


def test_markdown_states_when_baseline_and_cost_are_unavailable(
    sample_report: PipelineRunReport,
) -> None:
    report = sample_report.model_copy(
        update={
            "baseline": BaselineComparison(),
            "runtime": sample_report.runtime.model_copy(
                update={"estimated_cost": None}
            ),
        }
    )

    text = render_markdown(report)

    assert "无可比基线" in text
    assert "预估成本：不可用" in text


def test_markdown_renders_release_gate_section() -> None:
    report = PipelineRunReport(
        run_id="run-test",
        material_id="nm_demo",
        command="pipeline full",
        status=RunStatus.DEGRADED,
        started_at=datetime(2026, 7, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 1, 1, 1, tzinfo=timezone.utc),
        duration_ms=60000,
        release_gate=ReleaseGateReport(
            decision="hold",
            release_status="degraded",
            allow_degraded_sync=False,
            override=False,
            reasons=("worldbuilding_degraded",),
        ),
    )

    markdown = render_markdown(report)

    assert "## 发布门禁" in markdown
    assert "- 发布状态：degraded" in markdown
    assert "- 同步决策：hold" in markdown
    assert "- 阻断原因：worldbuilding_degraded" in markdown
