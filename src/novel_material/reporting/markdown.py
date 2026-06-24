"""将稳定报告模型渲染为确定性 Markdown。"""

from __future__ import annotations

import json
from typing import Any

from novel_material.audit.models import AuditSeverity, ReviewState
from novel_material.run_logging.redaction import sanitize_value

from .models import PipelineRunReport


_SEVERITY_ORDER = {
    AuditSeverity.BLOCKER: 0,
    AuditSeverity.ERROR: 1,
    AuditSeverity.WARNING: 2,
    AuditSeverity.INFO: 3,
}


def render_markdown(report: PipelineRunReport) -> str:
    """用固定栏目渲染一份不含 Rich markup 的 Markdown 报告。"""
    lines = [
        "# 运行与产物质量报告",
        "",
        "## 结论",
        "",
        f"- 状态：{report.status.value}",
        f"- 素材：{_text('material_id', report.material_id)}",
        f"- 命令：{_text('command', report.command)}",
        f"- 运行 ID：{_text('run_id', report.run_id)}",
        f"- 开始时间：{report.started_at.isoformat()}",
        f"- 完成时间：{report.completed_at.isoformat()}",
        f"- 总耗时：{_duration(report.duration_ms)}",
        f"- 同素材基线：{_baseline_text(report)}",
        "",
        "## 运行情况",
        "",
        (
            f"- API 调用：尝试 {report.runtime.operation_attempts}，"
            f"完成 {report.runtime.operation_completed}"
        ),
        (
            f"- Token：输入 {report.runtime.input_tokens}，"
            f"输出 {report.runtime.output_tokens}，"
            f"推理 {report.runtime.reasoning_tokens}，"
            f"总计 {report.runtime.total_tokens}"
        ),
        f"- 预估成本：{_cost_text(report.runtime.estimated_cost)}",
        f"- 诊断计数：{_text('diagnostic_counts', report.runtime.diagnostic_counts)}",
        "",
        "## 阶段",
        "",
        "| 阶段 | 状态 | 耗时 | 计数 | 诊断代码 |",
        "| --- | --- | ---: | --- | --- |",
    ]

    if report.stages:
        for stage in report.stages:
            lines.append(
                "| "
                + " | ".join(
                    (
                        _text("stage_name", stage.name),
                        stage.status.value,
                        _duration(stage.duration_ms),
                        _text("counts", stage.counts),
                        _text("diagnostic_codes", stage.diagnostic_codes),
                    )
                )
                + " |"
            )
    else:
        lines.append("| 无 | - | - | - | - |")

    quality = report.artifact_quality
    summary = quality.summary
    lines.extend(
        (
            "",
            "## 产物质量",
            "",
            f"- 检查项：{_text('checks', quality.checks) if quality.checks else '无'}",
            (
                "- 问题汇总："
                f"blocker={summary.blocker}，error={summary.error}，"
                f"warning={summary.warning}，info={summary.info}，"
                "因预算未复审="
                f"{summary.not_reviewed_due_to_budget}"
            ),
            (
                "- 复审预算："
                f"模式 {quality.review_budget.mode}，"
                f"调用 {quality.review_budget.calls_used}/"
                f"{quality.review_budget.max_calls}，"
                f"耗时 {quality.review_budget.elapsed_seconds:.2f}/"
                f"{quality.review_budget.max_seconds:.2f} 秒，"
                f"停止原因 {_text('stop_reason', quality.review_budget.stop_reason or '无')}"
            ),
            "",
            "## 问题与风险",
            "",
        )
    )

    issues = sorted(
        quality.issues,
        key=lambda issue: (_SEVERITY_ORDER[issue.severity], issue.code),
    )
    if not issues:
        lines.append("未发现问题。")
    for issue in issues:
        lines.extend(
            (
                f"### {issue.severity.value} · {_text('code', issue.code)}",
                "",
                f"- 产物：{_text('artifact', issue.artifact)}",
                f"- 说明：{_text('message', issue.message)}",
                f"- 证据：{_text('evidence', issue.evidence) if issue.evidence else '无'}",
                "",
            )
        )

    unreviewed = [
        issue
        for issue in issues
        if issue.review_state is ReviewState.NOT_REVIEWED_DUE_TO_BUDGET
    ]
    lines.extend(("## 未复审项", ""))
    if unreviewed:
        lines.extend(f"- {_text('code', issue.code)}" for issue in unreviewed)
    else:
        lines.append("无。")

    lines.extend(("", "## 下一步", ""))
    if report.next_actions:
        lines.extend(
            f"- {_text('next_action', action)}" for action in report.next_actions
        )
    else:
        lines.append("无。")
    return "\n".join(lines).rstrip() + "\n"


def _baseline_text(report: PipelineRunReport) -> str:
    baseline = report.baseline
    if baseline.kind == "unavailable" or baseline.baseline_duration_ms is None:
        return "无可比基线"
    delta = (
        "变化不可用"
        if baseline.delta_percent is None
        else f"变化 {baseline.delta_percent:+.2f}%"
    )
    return f"{_duration(baseline.baseline_duration_ms)}，{delta}"


def _cost_text(value: float | None) -> str:
    return "不可用" if value is None else f"{value:.6f}"


def _duration(value_ms: float) -> str:
    return f"{value_ms / 1000:.2f} 秒"


def _text(key: str, value: Any) -> str:
    cleaned = sanitize_value(key, value)
    if isinstance(cleaned, (dict, list, tuple)):
        rendered = json.dumps(
            cleaned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        rendered = str(cleaned)
    return rendered.replace("|", "\\|")


__all__ = ["render_markdown"]
