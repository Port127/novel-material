from novel_material.reporting.markdown import render_markdown
from novel_material.reporting.models import BaselineComparison, PipelineRunReport


def test_markdown_contains_conclusion_risks_and_next_actions(
    sample_report: PipelineRunReport,
) -> None:
    text = render_markdown(sample_report)

    assert "# 运行与产物质量报告" in text
    assert "状态：degraded" in text
    assert "API 调用：尝试 2，完成 1" in text
    assert "character_profile_fallback" in text
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
