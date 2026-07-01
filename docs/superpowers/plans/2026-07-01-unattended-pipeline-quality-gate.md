# 无人值守流水线质量门 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `nm pipeline full/continue --mode standard` 默认只同步可发布素材，并为降级素材提供可审计的人工放行路径。

**Architecture:** 在现有 `StageResult`/`RunStatus` 契约上新增 `release_gate` 阶段，不扩展状态枚举。阶段产物质量通过 `diagnostics` 与 `outputs` 表达，报告层从阶段事件中提取发布门禁摘要，`sync` 只在门禁允许时执行。

**Tech Stack:** Python 3、Typer、Pydantic、YAML、pytest、现有 Novel Material pipeline/runtime/reporting/storage 模块。

---

## 文件结构

- Create: `src/novel_material/pipeline/release_gate.py`  
  负责读取阶段结果、audit 摘要和关键产物信号，输出 `StageResult(name="release_gate")`。
- Modify: `src/novel_material/cli/pipeline.py`  
  给统一入口 `full` 和 `continue` 增加 `--allow-degraded-sync`，传入 `run_full_pipeline`/`run_continue_pipeline`。
- Modify: `src/novel_material/cli/pipeline_common.py`  
  在 `audit` 后、`sync` 前插入 `release_gate`；`sync` 启用条件改为读取门禁决策。
- Modify: `src/novel_material/pipeline/orchestrator.py`  
  让 `RunRequest.options` 持有已完成阶段快照，供后续阶段读取前序结果；`plan_continue()` 纳入 `release_gate`。
- Modify: `src/novel_material/pipeline/stages.py`  
  暴露 `run_release_gate_stage()`。
- Modify: `src/novel_material/reporting/models.py`  
  新增 `ReleaseGateReport`，挂到 `PipelineRunReport.release_gate`。
- Modify: `src/novel_material/reporting/builder.py`  
  从 `StageCompleted(release_gate)` 事件提取 `outputs`，构建报告门禁摘要。
- Modify: `src/novel_material/reporting/markdown.py`  
  增加“发布门禁”区块。
- Modify: `src/novel_material/infra/config_service.py`  
  暴露大上下文预算键，并修正 `LLM_CHARACTERS_SUMMARY_TOKENS` 键名。
- Modify: `config/settings.yaml`  
  增加质量优先预算与 insights 阈值配置。
- Create: `src/novel_material/infra/llm_budget.py`  
  提供 `budget_after_length_finish()` 纯函数，先覆盖截断扩预算决策。
- Modify: `src/novel_material/pipeline/analyze_validators.py`  
  对 `pacing=None` 做字段级恢复并写入 `quality.fallback_fields`。
- Modify: `src/novel_material/pipeline/worldbuilding.py`  
  返回结构化 `StageResult`，空结构不再是 success。
- Modify: `src/novel_material/pipeline/characters_core.py`  
  返回结构化 `StageResult`，完整小传全失败时降级。
- Modify: `src/novel_material/pipeline/work_profile.py`  
  返回结构化 `StageResult` 与专用诊断码。
- Modify: `src/novel_material/storage/sync_core.py`  
  在 `sync` 输出中记录门禁摘要；发布判断仍由 `release_gate` 完成。
- Test: `tests/pipeline/test_release_gate.py`
- Test: `tests/cli/test_pipeline_common.py`
- Test: `tests/reporting/test_builder.py`
- Test: `tests/reporting/test_markdown.py`
- Test: `tests/infra/test_config_service.py`
- Test: `tests/infra/test_llm_budget.py`
- Test: `tests/pipeline/test_analyze_field_fallback.py`
- Test: `tests/pipeline/test_worldbuilding_stage_result.py`
- Test: `tests/pipeline/test_work_profile_stage.py`

## 实施顺序

1. 发布门禁最先落地，先停止软失败同步泄漏。
2. 报告和 CLI 随门禁同包完成，保证用户看到一致结论。
3. 大上下文预算和 `pacing` 字段恢复作为第二层质量保障。
4. 阶段状态语义修正在门禁之后做，避免一次提交改动面过宽。
5. 每个任务独立提交，提交正文写明“主要改动”和“验证结果”。

### Task 1: Release Gate 判定核心

**Files:**
- Create: `src/novel_material/pipeline/release_gate.py`
- Test: `tests/pipeline/test_release_gate.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/pipeline/test_release_gate.py
from novel_material.pipeline.release_gate import evaluate_release_gate
from novel_material.runtime.contracts import Diagnostic, RunStatus, StageResult


def stage(name: str, status: RunStatus, *, outputs=None, diagnostics=()):
    return StageResult(
        stage_id=f"stage-{name}",
        name=name,
        status=status,
        outputs=outputs or {},
        diagnostics=diagnostics,
    )


def test_audit_error_blocks_sync() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage(
                "audit",
                RunStatus.DEGRADED,
                outputs={"summary": {"error": 1, "blocker": 0}},
            ),
        ),
        mode="standard",
        allow_degraded_sync=False,
    )

    assert result.status is RunStatus.FAILED
    assert result.outputs["decision"] == "block"
    assert result.outputs["release_status"] == "failed"
    assert "audit_error" in result.outputs["reasons"]


def test_degraded_hold_can_be_overridden() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage("worldbuilding", RunStatus.DEGRADED),
            stage("audit", RunStatus.SUCCESS),
        ),
        mode="standard",
        allow_degraded_sync=True,
    )

    assert result.status is RunStatus.SUCCESS
    assert result.outputs["decision"] == "allow"
    assert result.outputs["release_status"] == "degraded"
    assert result.outputs["override"] is True


def test_failed_stage_cannot_be_overridden() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.FAILED),
            stage("audit", RunStatus.SUCCESS),
        ),
        mode="standard",
        allow_degraded_sync=True,
    )

    assert result.status is RunStatus.FAILED
    assert result.outputs["decision"] == "block"
    assert result.outputs["override"] is False


def test_profile_missing_blocks_standard() -> None:
    result = evaluate_release_gate(
        "nm_demo",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage("audit", RunStatus.SUCCESS),
        ),
        mode="standard",
        allow_degraded_sync=False,
    )

    assert result.status is RunStatus.FAILED
    assert result.outputs["decision"] == "block"
    assert "profile_missing" in result.outputs["reasons"]
```

- [ ] **Step 2: 确认测试失败**

Run: `pytest tests/pipeline/test_release_gate.py -q`

Expected: FAIL，提示 `ModuleNotFoundError: No module named 'novel_material.pipeline.release_gate'`。

- [ ] **Step 3: 实现门禁纯逻辑**

```python
# src/novel_material/pipeline/release_gate.py
from __future__ import annotations

from collections.abc import Iterable

from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import Diagnostic, RunStatus, StageResult


CORE_FAILED_STAGES = {"analyze", "refine", "sync"}
DEGRADED_HOLD_STAGES = {"worldbuilding", "characters", "insights"}


def evaluate_release_gate(
    material_id: str,
    stages: Iterable[StageResult],
    *,
    mode: str,
    allow_degraded_sync: bool,
) -> StageResult:
    items = tuple(stages)
    by_name = {item.name: item for item in items}
    reasons: list[str] = []
    hold_reasons: list[str] = []

    for item in items:
        if item.name in CORE_FAILED_STAGES and item.status is RunStatus.FAILED:
            reasons.append(f"{item.name}_failed")

    audit = by_name.get("audit")
    audit_summary = audit.outputs.get("summary", {}) if audit else {}
    blocker_count = int(audit_summary.get("blocker", 0) or 0)
    error_count = int(audit_summary.get("error", 0) or 0)
    if blocker_count > 0:
        reasons.append("audit_blocker")
    if error_count > 0:
        reasons.append("audit_error")

    if mode in {"standard", "deep"} and by_name.get("profile") is None:
        reasons.append("profile_missing")
    profile = by_name.get("profile")
    if mode in {"standard", "deep"} and profile and profile.status is RunStatus.FAILED:
        reasons.append("profile_failed")

    for item in items:
        if item.name in DEGRADED_HOLD_STAGES and item.status is RunStatus.DEGRADED:
            hold_reasons.append(f"{item.name}_degraded")

    override = False
    if reasons:
        decision = "block"
        release_status = "failed"
        status = RunStatus.FAILED
    elif hold_reasons and allow_degraded_sync:
        decision = "allow"
        release_status = "degraded"
        override = True
        status = RunStatus.SUCCESS
    elif hold_reasons:
        decision = "hold"
        release_status = "degraded"
        status = RunStatus.DEGRADED
    else:
        decision = "allow"
        release_status = "success"
        status = RunStatus.SUCCESS

    context = current_context()
    diagnostics = (
        Diagnostic(
            code="release_gate_held" if status is RunStatus.DEGRADED else "release_gate_blocked",
            message="发布门禁未允许默认同步",
            severity="warning" if status is RunStatus.DEGRADED else "error",
            retryable=True,
            next_action="检查 reports/latest.md，修复问题后继续流水线",
        ),
    ) if status is not RunStatus.SUCCESS else ()

    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="release_gate",
        status=status,
        diagnostics=diagnostics,
        outputs={
            "material_id": material_id,
            "decision": decision,
            "release_status": release_status,
            "allow_degraded_sync": allow_degraded_sync,
            "override": override,
            "reasons": tuple(reasons or hold_reasons),
        },
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/pipeline/test_release_gate.py -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/pipeline/release_gate.py tests/pipeline/test_release_gate.py
git commit -m "feat(pipeline): 增加发布门禁判定核心" -m "主要改动：
- 新增 release_gate 纯判定逻辑
- 覆盖 audit error、degraded 人工放行、failed 不可放行和 profile 缺失规则

验证结果：
- pytest tests/pipeline/test_release_gate.py -q 通过"
```

### Task 2: Pipeline 接入门禁与 CLI 参数

**Files:**
- Modify: `src/novel_material/cli/pipeline.py`
- Modify: `src/novel_material/cli/pipeline_common.py`
- Modify: `src/novel_material/pipeline/orchestrator.py`
- Modify: `src/novel_material/pipeline/stages.py`
- Test: `tests/cli/test_pipeline_common.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_pipeline_common.py 追加
def test_stage_plan_places_release_gate_between_audit_and_sync():
    specs = pipeline_common._stage_specs(
        "nm_demo",
        {"mode": "standard"},
        elapsed_provider=lambda: 0.0,
    )

    names = [item.name for item in specs]
    assert names[-3:] == ["audit", "release_gate", "sync"]
    assert next(item for item in specs if item.name == "release_gate").blocking is True


def test_sync_runs_only_when_release_gate_allows(monkeypatch):
    executed = []
    specs = pipeline_common._stage_specs(
        "nm_demo",
        {"mode": "standard", "skip_sync": False},
        elapsed_provider=lambda: 0.0,
    )
    sync = next(item for item in specs if item.name == "sync")
    request = RunRequest(
        run_id="run-test",
        command="pipeline full",
        material_id="nm_demo",
        options={"completed_stages": (StageResult(
            stage_id="stage-release",
            name="release_gate",
            status=RunStatus.DEGRADED,
            outputs={"decision": "hold"},
        ),)},
    )

    monkeypatch.setattr(pipeline_common, "sync_novel", lambda *args, **kwargs: executed.append(args) or StageResult(
        stage_id="stage-sync",
        name="sync",
        status=RunStatus.SUCCESS,
    ))

    assert sync.enabled(request) is False
    assert executed == []


def test_sync_runs_when_release_gate_decision_is_allow():
    specs = pipeline_common._stage_specs(
        "nm_demo",
        {"mode": "standard", "skip_sync": False},
        elapsed_provider=lambda: 0.0,
    )
    sync = next(item for item in specs if item.name == "sync")
    request = RunRequest(
        run_id="run-test",
        command="pipeline full",
        material_id="nm_demo",
        options={"completed_stages": (StageResult(
            stage_id="stage-release",
            name="release_gate",
            status=RunStatus.SUCCESS,
            outputs={"decision": "allow"},
        ),)},
    )

    assert sync.enabled(request) is True
```

- [ ] **Step 2: 确认测试失败**

Run: `pytest tests/cli/test_pipeline_common.py::test_stage_plan_places_release_gate_between_audit_and_sync tests/cli/test_pipeline_common.py::test_sync_runs_only_when_release_gate_allows tests/cli/test_pipeline_common.py::test_sync_runs_when_release_gate_decision_is_allow -q`

Expected: FAIL，当前阶段列表没有 `release_gate`，`sync.enabled` 不读取门禁。

- [ ] **Step 3: 修改 `orchestrator` 注入已完成阶段**

```python
# src/novel_material/pipeline/orchestrator.py
# 在每个阶段 execute 前构造 stage_request
stage_request = request.model_copy(
    update={
        "options": {
            **request.options,
            "completed_stages": (*self._prior_stages, *tuple(results)),
        }
    }
)
result = spec.execute(stage_request)
```

保留现有异常处理分支；只把 `spec.execute(request)` 替换为 `spec.execute(stage_request)`。

- [ ] **Step 4: 修改 continue 阶段顺序**

```python
# src/novel_material/pipeline/orchestrator.py
order = (
    (("evaluation",) if include_navigation else ())
    + (
        "analyze",
        "outline",
        "worldbuilding",
        "characters",
        "tags",
        "insights",
        "refine",
        "profile",
        "audit",
        "release_gate",
        "sync",
    )
)
```

- [ ] **Step 5: 暴露 stage entry**

```python
# src/novel_material/pipeline/stages.py
from .release_gate import evaluate_release_gate


def run_release_gate_stage(material_id: str, **kwargs):
    return evaluate_release_gate(material_id, **kwargs)


__all__ = [
    "run_analyze_stage",
    "run_artifact_audit_stage",
    "run_characters_stage",
    "run_evaluation_stage",
    "run_ingest_stage",
    "run_insights_stage",
    "run_outline_stage",
    "run_profile_stage",
    "run_refine_stage",
    "run_release_gate_stage",
    "run_tags_stage",
    "run_worldbuilding_stage",
]
```

- [ ] **Step 6: 修改 `pipeline_common` 阶段计划**

```python
# src/novel_material/cli/pipeline_common.py
from novel_material.pipeline.stages import (
    run_analyze_stage,
    run_artifact_audit_stage,
    run_characters_stage,
    run_evaluation_stage,
    run_ingest_stage,
    run_insights_stage,
    run_outline_stage,
    run_profile_stage,
    run_refine_stage,
    run_release_gate_stage,
    run_tags_stage,
    run_worldbuilding_stage,
)


def _completed_stages(request: RunRequest) -> tuple[StageResult, ...]:
    value = request.options.get("completed_stages", ())
    return tuple(item for item in value if isinstance(item, StageResult))


def _release_gate_allows_sync(request: RunRequest) -> bool:
    gate = next(
        (item for item in reversed(_completed_stages(request)) if item.name == "release_gate"),
        None,
    )
    return gate is not None and gate.outputs.get("decision") == "allow"
```

在 `_stage_specs()` 的 `audit` 后插入：

```python
StageSpec(
    "release_gate",
    lambda request: run_release_gate_stage(
        material_id,
        stages=_completed_stages(request),
        mode=runtime_mode_name,
        allow_degraded_sync=bool(options.get("allow_degraded_sync")),
    ),
    blocking=True,
),
StageSpec(
    "sync",
    lambda _request: sync_novel(
        material_id,
        provider=provider,
        use_window=bool(options.get("use_window")),
        repair_allowed=False,
    ),
    blocking=True,
    enabled=lambda request: (
        not bool(options.get("skip_sync")) and _release_gate_allows_sync(request)
    ),
),
```

- [ ] **Step 7: 增加 CLI 参数**

```python
# src/novel_material/cli/pipeline.py
allow_degraded_sync: bool = typer.Option(
    False,
    "--allow-degraded-sync",
    help="允许 release_gate 判定为 degraded 的素材继续同步；failed 不可放行",
),
```

在 `cmd_full()` 和 `cmd_continue()` 调用中传入：

```python
allow_degraded_sync=allow_degraded_sync,
```

- [ ] **Step 8: 跑接入测试**

Run: `pytest tests/cli/test_pipeline_common.py -q`

Expected: PASS。

- [ ] **Step 9: 提交**

```bash
git add src/novel_material/cli/pipeline.py src/novel_material/cli/pipeline_common.py src/novel_material/pipeline/orchestrator.py src/novel_material/pipeline/stages.py tests/cli/test_pipeline_common.py
git commit -m "feat(pipeline): 接入发布门禁和降级同步参数" -m "主要改动：
- 在 audit 与 sync 之间插入 release_gate
- sync 启用条件改为读取 release_gate 决策
- full 和 continue 增加 --allow-degraded-sync 参数

验证结果：
- pytest tests/cli/test_pipeline_common.py -q 通过"
```

### Task 3: 报告展示发布门禁

**Files:**
- Modify: `src/novel_material/reporting/models.py`
- Modify: `src/novel_material/reporting/builder.py`
- Modify: `src/novel_material/reporting/markdown.py`
- Test: `tests/reporting/test_builder.py`
- Test: `tests/reporting/test_markdown.py`

- [ ] **Step 1: 写 builder 失败测试**

```python
# tests/reporting/test_builder.py 追加
def test_builder_extracts_release_gate_summary() -> None:
    events = run_events()
    started = events[0].occurred_at
    events.insert(
        -1,
        event(
            "StageCompleted",
            occurred_at=started + timedelta(seconds=12),
            stage_id="stage-release",
            material_id="nm_demo",
            command="pipeline full",
            status="degraded",
            duration_ms=12,
            attributes={
                "stage_name": "release_gate",
                "counts": {},
                "diagnostics": [{"code": "release_gate_held"}],
                "outputs": {
                    "decision": "hold",
                    "release_status": "degraded",
                    "allow_degraded_sync": False,
                    "override": False,
                    "reasons": ["worldbuilding_degraded"],
                },
            },
        ),
    )

    report = build_run_report(events)

    assert report.release_gate.decision == "hold"
    assert report.release_gate.release_status == "degraded"
    assert report.release_gate.reasons == ("worldbuilding_degraded",)
```

- [ ] **Step 2: 写 markdown 失败测试**

```python
# tests/reporting/test_markdown.py 追加
from datetime import datetime, timezone

from novel_material.reporting.markdown import render_markdown
from novel_material.reporting.models import PipelineRunReport, ReleaseGateReport
from novel_material.runtime.contracts import RunStatus


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
```

- [ ] **Step 3: 确认测试失败**

Run: `pytest tests/reporting/test_builder.py::test_builder_extracts_release_gate_summary tests/reporting/test_markdown.py::test_markdown_renders_release_gate_section -q`

Expected: FAIL，`PipelineRunReport` 没有 `release_gate`。

- [ ] **Step 4: 增加报告模型**

```python
# src/novel_material/reporting/models.py
class ReleaseGateReport(BaseModel):
    """发布门禁摘要，不包含领域正文。"""

    model_config = ConfigDict(frozen=True)

    decision: str = "not_evaluated"
    release_status: str = "unknown"
    allow_degraded_sync: bool = False
    override: bool = False
    reasons: tuple[str, ...] = ()


class PipelineRunReport(BaseModel):
    ...
    release_gate: ReleaseGateReport = Field(default_factory=ReleaseGateReport)
```

把 `ReleaseGateReport` 加入 `__all__`。

- [ ] **Step 5: StageCompleted 事件带 outputs**

```python
# src/novel_material/pipeline/orchestrator.py
attributes={
    "stage_name": spec.name,
    "counts": result.counts.model_dump(mode="json"),
    "diagnostics": [
        item.model_dump(mode="json")
        for item in result.diagnostics
    ],
    "outputs": result.outputs,
}
```

- [ ] **Step 6: builder 提取门禁**

```python
# src/novel_material/reporting/builder.py
from .models import ReleaseGateReport


def _release_gate_report(events: list[RunEvent]) -> ReleaseGateReport:
    for item in reversed(events):
        if item.event_name != "StageCompleted":
            continue
        if item.attributes.get("stage_name") != "release_gate":
            continue
        outputs = item.attributes.get("outputs")
        if not isinstance(outputs, Mapping):
            return ReleaseGateReport()
        return ReleaseGateReport(
            decision=str(outputs.get("decision") or "not_evaluated"),
            release_status=str(outputs.get("release_status") or "unknown"),
            allow_degraded_sync=bool(outputs.get("allow_degraded_sync")),
            override=bool(outputs.get("override")),
            reasons=tuple(str(reason) for reason in outputs.get("reasons", ()) if str(reason)),
        )
    return ReleaseGateReport()
```

在 `PipelineRunReport(...)` 构造中传入：

```python
release_gate=_release_gate_report(ordered),
```

- [ ] **Step 7: markdown 增加区块**

```python
# src/novel_material/reporting/markdown.py
gate = report.release_gate
lines.extend(
    (
        "",
        "## 发布门禁",
        "",
        f"- 发布状态：{_text('release_status', gate.release_status)}",
        f"- 同步决策：{_text('decision', gate.decision)}",
        f"- 人工放行：{'true' if gate.override else 'false'}",
    )
)
if gate.reasons:
    lines.append(f"- 阻断原因：{_text('reasons', gate.reasons)}")
else:
    lines.append("- 阻断原因：无")
```

- [ ] **Step 8: 跑报告测试**

Run: `pytest tests/reporting/test_builder.py tests/reporting/test_markdown.py -q`

Expected: PASS。

- [ ] **Step 9: 提交**

```bash
git add src/novel_material/reporting/models.py src/novel_material/reporting/builder.py src/novel_material/reporting/markdown.py src/novel_material/pipeline/orchestrator.py tests/reporting/test_builder.py tests/reporting/test_markdown.py
git commit -m "feat(reporting): 展示发布门禁结论" -m "主要改动：
- 报告模型增加 release_gate 摘要
- 报告构建器从 release_gate 阶段输出提取发布状态
- Markdown 报告展示发布状态、同步决策和人工放行

验证结果：
- pytest tests/reporting/test_builder.py tests/reporting/test_markdown.py -q 通过"
```

### Task 4: 大上下文预算配置与截断决策

**Files:**
- Modify: `config/settings.yaml`
- Modify: `src/novel_material/infra/config_service.py`
- Create: `src/novel_material/infra/llm_budget.py`
- Test: `tests/infra/test_config_service.py`
- Test: `tests/infra/test_llm_budget.py`

- [ ] **Step 1: 写配置失败测试**

```python
# tests/infra/test_config_service.py 追加
def test_build_llm_config_exposes_quality_budget_keys() -> None:
    config = _build_llm_config(
        {
            "LLM_CONTEXT_WINDOW_TOKENS": 1000000,
            "LLM_WORLDBUILDING_MAX_TOKENS": 64000,
            "LLM_CHARACTERS_MAX_TOKENS": 64000,
            "LLM_PROFILE_MAX_TOKENS": 64000,
            "LLM_INSIGHTS_MAX_TOKENS": 32000,
            "LLM_CHARACTERS_SUMMARY_TOKENS": 120000,
            "LLM_PROFILE_CONTEXT_TOKENS": 120000,
            "LLM_LENGTH_RETRY_MULTIPLIER": 2,
            "LLM_LENGTH_RETRY_MAX_TOKENS": 128000,
        },
        providers_yaml=None,
        provider=None,
    )

    assert config["context_window_tokens"] == 1000000
    assert config["worldbuilding_max_tokens"] == 64000
    assert config["characters_max_tokens"] == 64000
    assert config["profile_max_tokens"] == 64000
    assert config["insights_max_tokens"] == 32000
    assert config["characters_summary_tokens"] == 120000
    assert config["profile_context_tokens"] == 120000
    assert config["length_retry_multiplier"] == 2
    assert config["length_retry_max_tokens"] == 128000
```

- [ ] **Step 2: 写预算纯函数失败测试**

```python
# tests/infra/test_llm_budget.py
from novel_material.infra.llm_budget import budget_after_length_finish


def test_length_finish_expands_budget_with_diagnostic() -> None:
    decision = budget_after_length_finish(
        current_max_tokens=8000,
        stage_max_tokens=64000,
        multiplier=2,
    )

    assert decision.next_max_tokens == 16000
    assert decision.diagnostic_code == "llm_budget_expanded"
    assert decision.should_retry is True


def test_length_finish_requires_split_at_cap() -> None:
    decision = budget_after_length_finish(
        current_max_tokens=64000,
        stage_max_tokens=64000,
        multiplier=2,
    )

    assert decision.next_max_tokens == 64000
    assert decision.diagnostic_code == "llm_task_split_required"
    assert decision.should_retry is False
```

- [ ] **Step 3: 确认测试失败**

Run: `pytest tests/infra/test_config_service.py::test_build_llm_config_exposes_quality_budget_keys tests/infra/test_llm_budget.py -q`

Expected: FAIL，配置键和模块尚不存在。

- [ ] **Step 4: 修改 `config_service`**

```python
# src/novel_material/infra/config_service.py
base_config = {
    ...
    "context_window_tokens": int(settings.get("LLM_CONTEXT_WINDOW_TOKENS", 1000000)),
    "quality_budget_mode": settings.get("LLM_QUALITY_BUDGET_MODE", "quality"),
    "worldbuilding_max_tokens": int(settings.get("LLM_WORLDBUILDING_MAX_TOKENS", 64000)),
    "characters_max_tokens": int(settings.get("LLM_CHARACTERS_MAX_TOKENS", 64000)),
    "profile_max_tokens": int(settings.get("LLM_PROFILE_MAX_TOKENS", 64000)),
    "insights_max_tokens": int(settings.get("LLM_INSIGHTS_MAX_TOKENS", 32000)),
    "outline_summary_tokens": int(settings.get("LLM_OUTLINE_SUMMARY_TOKENS", 80000)),
    "outline_seq_summary_tokens": int(settings.get("LLM_OUTLINE_SEQ_SUMMARY_TOKENS", 8000)),
    "worldbuilding_summary_tokens": int(settings.get("LLM_WORLDBUILDING_SUMMARY_TOKENS", 120000)),
    "characters_summary_tokens": int(settings.get("LLM_CHARACTERS_SUMMARY_TOKENS", 120000)),
    "profile_context_tokens": int(settings.get("LLM_PROFILE_CONTEXT_TOKENS", 120000)),
    "length_retry_multiplier": int(settings.get("LLM_LENGTH_RETRY_MULTIPLIER", 2)),
    "length_retry_max_tokens": int(settings.get("LLM_LENGTH_RETRY_MAX_TOKENS", 128000)),
    ...
}
```

- [ ] **Step 5: 增加预算纯函数**

```python
# src/novel_material/infra/llm_budget.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LengthRetryDecision:
    next_max_tokens: int
    diagnostic_code: str
    should_retry: bool


def budget_after_length_finish(
    *,
    current_max_tokens: int,
    stage_max_tokens: int,
    multiplier: int,
) -> LengthRetryDecision:
    if current_max_tokens < stage_max_tokens:
        next_tokens = min(stage_max_tokens, current_max_tokens * max(2, multiplier))
        return LengthRetryDecision(
            next_max_tokens=next_tokens,
            diagnostic_code="llm_budget_expanded",
            should_retry=True,
        )
    return LengthRetryDecision(
        next_max_tokens=stage_max_tokens,
        diagnostic_code="llm_task_split_required",
        should_retry=False,
    )


__all__ = ["LengthRetryDecision", "budget_after_length_finish"]
```

- [ ] **Step 6: 修改 settings**

```yaml
# config/settings.yaml
LLM_CONTEXT_WINDOW_TOKENS: 1000000
LLM_QUALITY_BUDGET_MODE: quality

LLM_WORLDBUILDING_MAX_TOKENS: 64000
LLM_CHARACTERS_MAX_TOKENS: 64000
LLM_PROFILE_MAX_TOKENS: 64000
LLM_INSIGHTS_MAX_TOKENS: 32000

LLM_OUTLINE_SUMMARY_TOKENS: 80000
LLM_WORLDBUILDING_SUMMARY_TOKENS: 120000
LLM_CHARACTERS_SUMMARY_TOKENS: 120000
LLM_PROFILE_CONTEXT_TOKENS: 120000

LLM_LENGTH_RETRY_MULTIPLIER: 2
LLM_LENGTH_RETRY_MAX_TOKENS: 128000

INSIGHTS_MIN_SUCCESS_RATE_STANDARD: 0.8
INSIGHTS_MIN_SUCCESS_RATE_DEEP: 0.95
```

- [ ] **Step 7: 跑配置与预算测试**

Run: `pytest tests/infra/test_config_service.py tests/infra/test_llm_budget.py -q`

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add config/settings.yaml src/novel_material/infra/config_service.py src/novel_material/infra/llm_budget.py tests/infra/test_config_service.py tests/infra/test_llm_budget.py
git commit -m "feat(llm): 增加质量优先大上下文预算" -m "主要改动：
- 增加阶段级大上下文预算配置
- 修正 characters_summary_tokens 的配置键读取
- 新增 length finish 后的预算扩展决策函数

验证结果：
- pytest tests/infra/test_config_service.py tests/infra/test_llm_budget.py -q 通过"
```

### Task 5: 章级 `pacing=None` 字段级恢复

**Files:**
- Modify: `src/novel_material/pipeline/analyze_validators.py`
- Test: `tests/pipeline/test_analyze_field_fallback.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/pipeline/test_analyze_field_fallback.py
import pytest

from novel_material.infra.llm_contracts import LLMResponseContractError
from novel_material.pipeline.analyze_validators import normalize_chapter_analysis_response


def base_payload(**overrides):
    payload = {
        "summary": "主角遇到强敌并被迫改变计划。",
        "pacing": "中",
        "key_event": "主角决定主动反击。",
        "hook_type": "危机",
        "characters_appear": ["主角"],
        "chapter_functions": ["战斗冲突"],
        "setting": ["城门"],
        "emotional_tone": ["紧张"],
        "scene_type": ["战斗"],
        "technique": ["悬念"],
        "tension_level": 5,
    }
    payload.update(overrides)
    return payload


def test_pacing_none_is_recovered_with_quality_marker() -> None:
    result = normalize_chapter_analysis_response(base_payload(pacing=None))

    assert result["pacing"] == "快"
    assert result["quality"]["fallback_fields"] == ["pacing"]
    assert "pacing" in result["quality"]["fallback_reason"]


def test_hard_fact_missing_still_fails() -> None:
    with pytest.raises(LLMResponseContractError):
        normalize_chapter_analysis_response(base_payload(summary=None))
```

- [ ] **Step 2: 确认测试失败**

Run: `pytest tests/pipeline/test_analyze_field_fallback.py -q`

Expected: FAIL，`pacing=None` 当前触发 `LLMResponseContractError`。

- [ ] **Step 3: 实现 fallback**

```python
# src/novel_material/pipeline/analyze_validators.py
def _recover_pacing(payload: dict) -> tuple[str, dict | None]:
    value = payload.get("pacing")
    if value is not None:
        return require_string(value, "chapter_analysis.pacing"), None

    tension = payload.get("tension_level")
    functions = [str(item) for item in payload.get("chapter_functions", []) or []]
    joined = " ".join(functions)
    if tension in (4, 5) or any(keyword in joined for keyword in ("战斗", "冲突", "追逃", "危机")):
        pacing = "快"
    elif tension in (1, 2) or any(keyword in joined for keyword in ("日常", "过渡", "铺垫", "休整")):
        pacing = "慢"
    else:
        pacing = "中"
    return pacing, {
        "fallback_fields": ["pacing"],
        "fallback_reason": {
            "pacing": "LLM 返回 null，按 tension_level/chapter_functions 推断",
        },
    }
```

在 `normalize_chapter_analysis_response()` 中先校验硬事实：

```python
for field in ("summary", "key_event", "hook_type"):
    result[field] = require_string(result.get(field), f"chapter_analysis.{field}")
...
tension = require_integer(result.get("tension_level"), "chapter_analysis.tension_level")
...
result["pacing"], quality = _recover_pacing(result)
if quality is not None:
    result["quality"] = quality
```

- [ ] **Step 4: 跑字段恢复测试**

Run: `pytest tests/pipeline/test_analyze_field_fallback.py tests/pipeline/test_llm_response_contracts.py -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/pipeline/analyze_validators.py tests/pipeline/test_analyze_field_fallback.py
git commit -m "fix(analyze): 恢复 pacing 空值并记录质量标记" -m "主要改动：
- pacing 为 null 时按张力和章节功能推断默认值
- 在章节分析结果写入 quality.fallback_fields 和 fallback_reason
- 保持 summary、key_event、hook_type 等硬事实字段严格校验

验证结果：
- pytest tests/pipeline/test_analyze_field_fallback.py tests/pipeline/test_llm_response_contracts.py -q 通过"
```

### Task 6: 世界观阶段返回结构化结果

**Files:**
- Modify: `src/novel_material/pipeline/worldbuilding.py`
- Test: `tests/pipeline/test_worldbuilding_stage_result.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/pipeline/test_worldbuilding_stage_result.py
from pathlib import Path

from novel_material.infra.yaml_io import save_yaml
from novel_material.pipeline.worldbuilding import generate_worldbuilding
from novel_material.runtime.contracts import RunStatus, StageResult


def test_worldbuilding_empty_fallback_is_degraded(tmp_path: Path, monkeypatch) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "name": "示例"})
    save_yaml(novel / "chapter_index.yaml", [{"chapter": 1, "title": "一"}])
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "公司竞争"}])

    monkeypatch.setattr("novel_material.pipeline.worldbuilding.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.load_config",
        lambda _provider=None: {"llm": {"worldbuilding_timeout": 1, "rate_limit_seconds": 0, "worldbuilding_summary_tokens": 1000}},
    )
    monkeypatch.setattr(
        "novel_material.pipeline.worldbuilding.call_llm",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("api down")),
    )

    result = generate_worldbuilding("nm_demo")

    assert isinstance(result, StageResult)
    assert result.status is RunStatus.DEGRADED
    assert result.outputs["llm_success"] is False
    assert result.outputs["entity_count"] == 0
    assert result.diagnostics[0].code == "worldbuilding_api_failed"
```

- [ ] **Step 2: 确认测试失败**

Run: `pytest tests/pipeline/test_worldbuilding_stage_result.py -q`

Expected: FAIL，当前 `generate_worldbuilding()` 返回 `True`。

- [ ] **Step 3: 修改返回值与诊断**

```python
# src/novel_material/pipeline/worldbuilding.py
from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import Diagnostic, ProgressCounts, RunStatus, StageResult


def _worldbuilding_stage_result(material_id: str, layered, *, elapsed: float, diagnostic: Diagnostic | None) -> StageResult:
    llm_success = bool(layered.index.llm_success)
    entity_count = int(layered.index.entity_count)
    relation_count = int(layered.index.relation_count)
    evidence_count = int(layered.index.evidence_count)
    status = RunStatus.SUCCESS if llm_success and (entity_count > 0 or evidence_count > 0) else RunStatus.DEGRADED
    context = current_context()
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="worldbuilding",
        status=status,
        counts=ProgressCounts(expected=1, processed=1, succeeded=1 if status is RunStatus.SUCCESS else 0, degraded=1 if status is RunStatus.DEGRADED else 0, remaining=0),
        duration_ms=elapsed * 1000,
        diagnostics=(diagnostic,) if diagnostic else (),
        outputs={
            "llm_success": llm_success,
            "entity_count": entity_count,
            "relation_count": relation_count,
            "evidence_count": evidence_count,
        },
    )
```

在异常分支设置：

```python
diagnostic = Diagnostic(
    code="worldbuilding_schema_invalid" if isinstance(e, LLMResponseContractError) else "worldbuilding_api_failed",
    message=f"世界观提取失败，已写入空结构: {type(e).__name__}",
    severity="warning",
    retryable=True,
    next_action=f"nm pipeline worldbuilding {material_id}",
)
```

将 `save_run_history(... status="success")` 改为：

```python
stage_result = _worldbuilding_stage_result(material_id, layered, elapsed=elapsed, diagnostic=diagnostic)
save_run_history(..., status=stage_result.status.value)
return stage_result
```

- [ ] **Step 4: 跑世界观测试**

Run: `pytest tests/pipeline/test_worldbuilding_stage_result.py tests/pipeline/test_stage_contracts.py -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/pipeline/worldbuilding.py tests/pipeline/test_worldbuilding_stage_result.py
git commit -m "fix(worldbuilding): 空结构兜底返回降级状态" -m "主要改动：
- 世界观阶段返回 StageResult
- LLM 调用失败或 schema 无效时写入结构化诊断
- run_history 状态与 StageResult 状态保持一致

验证结果：
- pytest tests/pipeline/test_worldbuilding_stage_result.py tests/pipeline/test_stage_contracts.py -q 通过"
```

### Task 7: Profile 阶段返回专用诊断

**Files:**
- Modify: `src/novel_material/pipeline/work_profile.py`
- Test: `tests/pipeline/test_work_profile_stage.py`

- [ ] **Step 1: 改写现有测试期望**

```python
# tests/pipeline/test_work_profile_stage.py
from novel_material.runtime.contracts import RunStatus, StageResult


# 在成功测试中替换断言
result = generate_work_profile("nm_demo")
assert isinstance(result, StageResult)
assert result.status is RunStatus.SUCCESS
assert result.outputs["work_profile_written"] is True


# 在缺事实测试中替换断言
result = generate_work_profile("nm_demo")
assert result.status is RunStatus.FAILED
assert result.diagnostics[0].code == "work_profile_evidence_missing"
assert not (tmp_path / "nm_demo" / "work_profile.yaml").exists()
```

追加 schema invalid 测试：

```python
def test_generate_work_profile_reports_schema_invalid(tmp_path: Path, monkeypatch) -> None:
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    save_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "name": "示例"})
    save_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "主角创业"}])
    monkeypatch.setattr("novel_material.pipeline.work_profile.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.pipeline.work_profile.load_config",
        lambda _provider=None: {"llm": {"profile_timeout": 1}},
    )
    monkeypatch.setattr("novel_material.pipeline.work_profile.call_llm", lambda *args, **kwargs: {"bad": "payload"})

    result = generate_work_profile("nm_demo")

    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "work_profile_schema_invalid"
```

- [ ] **Step 2: 确认测试失败**

Run: `pytest tests/pipeline/test_work_profile_stage.py -q`

Expected: FAIL，当前返回 bool。

- [ ] **Step 3: 实现 `StageResult` helper**

```python
# src/novel_material/pipeline/work_profile.py
from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import Diagnostic, ProgressCounts, RunStatus, StageResult


def _profile_result(status: RunStatus, *, diagnostic: Diagnostic | None = None, written: bool = False) -> StageResult:
    context = current_context()
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="profile",
        status=status,
        counts=ProgressCounts(
            expected=1,
            processed=1,
            succeeded=1 if status is RunStatus.SUCCESS else 0,
            failed=1 if status is RunStatus.FAILED else 0,
            remaining=0,
        ),
        diagnostics=(diagnostic,) if diagnostic else (),
        outputs={"work_profile_written": written},
    )
```

在 `context is None` 分支返回：

```python
return _profile_result(
    RunStatus.FAILED,
    diagnostic=Diagnostic(
        code="work_profile_evidence_missing",
        message="生成作品画像所需 meta.yaml 或 chapters.yaml 不完整",
        severity="error",
        retryable=True,
    ),
)
```

在异常分支区分校验失败与调用失败：

```python
except Exception as exc:
    code = "work_profile_schema_invalid" if exc.__class__.__name__.endswith("Error") else "work_profile_api_failed"
    return _profile_result(
        RunStatus.FAILED,
        diagnostic=Diagnostic(
            code=code,
            message=f"作品画像生成失败: {type(exc).__name__}",
            severity="error",
            retryable=True,
        ),
    )
```

成功写入后：

```python
return _profile_result(RunStatus.SUCCESS, written=True)
```

- [ ] **Step 4: 跑 profile 测试**

Run: `pytest tests/pipeline/test_work_profile_stage.py tests/pipeline/test_stage_contracts.py -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/pipeline/work_profile.py tests/pipeline/test_work_profile_stage.py
git commit -m "fix(profile): 返回作品画像阶段专用诊断" -m "主要改动：
- generate_work_profile 改为返回 StageResult
- 区分证据缺失、schema 无效和 API 调用失败
- 保留 work_profile_written 输出供门禁和报告使用

验证结果：
- pytest tests/pipeline/test_work_profile_stage.py tests/pipeline/test_stage_contracts.py -q 通过"
```

### Task 8: Characters 降级计数与门禁信号

**Files:**
- Modify: `src/novel_material/pipeline/characters_core.py`
- Test: `tests/pipeline/test_characters_stage_result.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/pipeline/test_characters_stage_result.py
from novel_material.pipeline.characters_core import _characters_stage_status
from novel_material.runtime.contracts import RunStatus


def test_all_biography_targets_failed_is_degraded() -> None:
    status, diagnostic = _characters_stage_status(
        biography_target_count=12,
        biography_completed_count=0,
        biography_failed_count=12,
        fallback_count=12,
    )

    assert status is RunStatus.DEGRADED
    assert diagnostic.code == "character_biography_all_failed"


def test_no_biography_target_can_succeed() -> None:
    status, diagnostic = _characters_stage_status(
        biography_target_count=0,
        biography_completed_count=0,
        biography_failed_count=0,
        fallback_count=0,
    )

    assert status is RunStatus.SUCCESS
    assert diagnostic is None
```

- [ ] **Step 2: 确认测试失败**

Run: `pytest tests/pipeline/test_characters_stage_result.py -q`

Expected: FAIL，helper 尚不存在。

- [ ] **Step 3: 增加状态 helper**

```python
# src/novel_material/pipeline/characters_core.py
from novel_material.runtime.contracts import Diagnostic, RunStatus, StageResult, ProgressCounts
from novel_material.runtime.context import current_context, new_id


def _characters_stage_status(
    *,
    biography_target_count: int,
    biography_completed_count: int,
    biography_failed_count: int,
    fallback_count: int,
) -> tuple[RunStatus, Diagnostic | None]:
    if biography_target_count > 0 and biography_completed_count == 0:
        return RunStatus.DEGRADED, Diagnostic(
            code="character_biography_all_failed",
            message="核心人物完整小传目标全部失败，已保留简档或 fallback 档案",
            severity="warning",
            retryable=True,
            next_action="nm pipeline characters <material_id>",
        )
    if biography_failed_count > 0 or fallback_count > 0:
        return RunStatus.DEGRADED, Diagnostic(
            code="character_biography_partial_failed",
            message="部分人物完整小传失败，已保留可用档案",
            severity="warning",
            retryable=True,
        )
    return RunStatus.SUCCESS, None
```

- [ ] **Step 4: 将 `generate_characters()` 末尾返回改为 `StageResult`**

```python
status, diagnostic = _characters_stage_status(
    biography_target_count=biography_summary["biography_target_count"],
    biography_completed_count=biography_summary["biography_completed_count"],
    biography_failed_count=biography_summary["biography_failed_count"],
    fallback_count=sum(1 for item in all_characters if item.get("profile_level") == "fallback"),
)
context = current_context()
return StageResult(
    stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
    name="characters",
    status=status,
    counts=ProgressCounts(
        expected=biography_summary["biography_target_count"],
        processed=biography_summary["biography_target_count"],
        succeeded=biography_summary["biography_completed_count"],
        degraded=biography_summary["biography_failed_count"],
        failed=0,
        remaining=0,
    ),
    diagnostics=(diagnostic,) if diagnostic else (),
    outputs={
        "character_count": len(all_characters),
        "fallback_count": sum(1 for item in all_characters if item.get("profile_level") == "fallback"),
        **biography_summary,
    },
)
```

保留早期目录不存在时的 `return False`，由 `adapt_stage_result()` 映射为 failed。

- [ ] **Step 5: 跑 characters 测试**

Run: `pytest tests/pipeline/test_characters_stage_result.py tests/pipeline/test_stage_contracts.py -q`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/pipeline/characters_core.py tests/pipeline/test_characters_stage_result.py
git commit -m "fix(characters): 标记人物小传降级状态" -m "主要改动：
- 人物阶段返回完整小传目标、完成、失败和 fallback 计数
- 核心人物完整小传全失败时返回 degraded
- 保持目录缺失等硬失败由旧适配器映射为 failed

验证结果：
- pytest tests/pipeline/test_characters_stage_result.py tests/pipeline/test_stage_contracts.py -q 通过"
```

### Task 9: Sync 记录门禁摘要

**Files:**
- Modify: `src/novel_material/cli/pipeline_common.py`
- Modify: `src/novel_material/storage/sync_core.py`
- Test: `tests/cli/test_pipeline_common.py`
- Test: `tests/storage/test_sync_core.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/storage/test_sync_core.py 追加
from novel_material.storage.sync_core import _sync_result
from novel_material.runtime.contracts import RunStatus


def test_sync_result_preserves_release_gate_summary() -> None:
    result = _sync_result(
        "nm_demo",
        RunStatus.SUCCESS,
        release_gate={"decision": "allow", "release_status": "degraded", "override": True},
    )

    assert result.outputs["release_gate"]["decision"] == "allow"
    assert result.outputs["release_gate"]["override"] is True
```

- [ ] **Step 2: 确认测试失败**

Run: `pytest tests/storage/test_sync_core.py::test_sync_result_preserves_release_gate_summary -q`

Expected: FAIL，`_sync_result()` 不接收 `release_gate`。

- [ ] **Step 3: 修改 sync 输出**

```python
# src/novel_material/storage/sync_core.py
def _sync_result(
    material_id: str,
    status: RunStatus,
    *,
    diagnostic: Diagnostic | None = None,
    release_gate: dict | None = None,
) -> StageResult:
    outputs = {"material_id": material_id}
    if release_gate is not None:
        outputs["release_gate"] = release_gate
    return StageResult(
        ...
        outputs=outputs,
    )
```

给 `_sync_novel_impl()` 和公开 `sync_novel()` 增加关键字参数：

```python
release_gate: dict | None = None,
```

所有 `_sync_result(...)` 调用传入 `release_gate=release_gate`。

- [ ] **Step 4: `pipeline_common` 传递门禁摘要**

```python
# src/novel_material/cli/pipeline_common.py
def _release_gate_outputs(request: RunRequest) -> dict | None:
    gate = next(
        (item for item in reversed(_completed_stages(request)) if item.name == "release_gate"),
        None,
    )
    return dict(gate.outputs) if gate is not None else None
```

在 `sync_novel()` 调用中传入：

```python
release_gate=_release_gate_outputs(request),
```

- [ ] **Step 5: 跑 sync 测试**

Run: `pytest tests/storage/test_sync_core.py tests/cli/test_pipeline_common.py -q`

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/cli/pipeline_common.py src/novel_material/storage/sync_core.py tests/cli/test_pipeline_common.py tests/storage/test_sync_core.py
git commit -m "feat(sync): 记录发布门禁同步摘要" -m "主要改动：
- sync 输出保留 release_gate 摘要
- pipeline_common 将门禁输出传入 sync 阶段
- 发布判断仍由 release_gate 负责，sync 只记录执行上下文

验证结果：
- pytest tests/storage/test_sync_core.py tests/cli/test_pipeline_common.py -q 通过"
```

### Task 10: 全局回归与人工事故夹具

**Files:**
- Create: `tests/pipeline/test_unattended_pipeline_regression.py`
- Modify: `tests/cli/test_pipeline_common.py`
- Modify: `tests/reporting/test_builder.py`

- [ ] **Step 1: 写 18cb 型软失败夹具测试**

```python
# tests/pipeline/test_unattended_pipeline_regression.py
from novel_material.pipeline.release_gate import evaluate_release_gate
from novel_material.runtime.contracts import RunStatus, StageResult


def stage(name: str, status: RunStatus, *, outputs=None):
    return StageResult(stage_id=f"stage-{name}", name=name, status=status, outputs=outputs or {})


def test_18cb_like_degraded_artifacts_do_not_sync_by_default() -> None:
    result = evaluate_release_gate(
        "nm_fixture_18cb",
        (
            stage("analyze", RunStatus.SUCCESS),
            stage("worldbuilding", RunStatus.DEGRADED, outputs={"llm_success": False, "entity_count": 0}),
            stage("characters", RunStatus.DEGRADED, outputs={"biography_target_count": 12, "biography_completed_count": 0}),
            stage("profile", RunStatus.FAILED),
            stage("audit", RunStatus.DEGRADED, outputs={"summary": {"error": 1, "blocker": 0}}),
        ),
        mode="standard",
        allow_degraded_sync=False,
    )

    assert result.outputs["decision"] == "block"
    assert result.status is RunStatus.FAILED
```

- [ ] **Step 2: 写 7u96 型字段恢复夹具测试**

```python
from novel_material.pipeline.analyze_validators import normalize_chapter_analysis_response


def test_7u96_like_pacing_null_is_warning_quality_fallback() -> None:
    result = normalize_chapter_analysis_response(
        {
            "summary": "这一章完成一次冲突升级，主角被迫正面应对敌人。",
            "pacing": None,
            "key_event": "主角在冲突中明确反击路线。",
            "hook_type": "危机",
            "characters_appear": ["主角"],
            "chapter_functions": ["战斗冲突"],
            "setting": ["擂台"],
            "emotional_tone": ["紧张"],
            "scene_type": ["战斗"],
            "technique": ["悬念"],
            "tension_level": 5,
        }
    )

    assert result["pacing"] == "快"
    assert result["quality"]["fallback_fields"] == ["pacing"]
```

- [ ] **Step 3: 确认夹具测试通过**

Run: `pytest tests/pipeline/test_unattended_pipeline_regression.py -q`

Expected: PASS。

- [ ] **Step 4: 跑全局相关回归**

Run: `pytest tests/pipeline tests/cli/test_pipeline_common.py tests/reporting tests/infra/test_config_service.py tests/infra/test_llm_budget.py tests/storage/test_sync_core.py -q`

Expected: PASS。

- [ ] **Step 5: 只读检查历史事故素材**

Run: `python -m novel_material.cli.main pipeline status nm_novel_20260701_7u96`

Expected: 命令只读输出状态，不修改 `data/novels/nm_novel_20260701_7u96`。

Run: `python -m novel_material.cli.main pipeline status nm_novel_20260701_18cb`

Expected: 命令只读输出状态，不修改 `data/novels/nm_novel_20260701_18cb`。

- [ ] **Step 6: 提交**

```bash
git add tests/pipeline/test_unattended_pipeline_regression.py tests/cli/test_pipeline_common.py tests/reporting/test_builder.py
git commit -m "test(pipeline): 增加无人值守事故回归夹具" -m "主要改动：
- 增加 18cb 型软失败阻断回归
- 增加 7u96 型 pacing 空值恢复回归
- 验证历史事故素材只读查看，不执行修复或重同步

验证结果：
- pytest tests/pipeline/test_unattended_pipeline_regression.py -q 通过
- pytest tests/pipeline tests/cli/test_pipeline_common.py tests/reporting tests/infra/test_config_service.py tests/infra/test_llm_budget.py tests/storage/test_sync_core.py -q 通过
- python -m novel_material.cli.main pipeline status nm_novel_20260701_7u96 只读执行
- python -m novel_material.cli.main pipeline status nm_novel_20260701_18cb 只读执行"
```

## 最终验收

- [ ] `nm pipeline full <file> --mode standard` 默认执行到 `release_gate` 后，只在 `decision=allow` 时进入 `sync`。
- [ ] `--allow-degraded-sync` 只放行 `degraded`，不能放行 `failed`。
- [ ] `reports/latest.md` 明确展示发布状态、同步决策、人工放行和原因。
- [ ] `reports/latest.yaml` 中 `release_gate`、阶段列表、run status 口径一致。
- [ ] `pacing=None` 只产生字段级质量标记，不导致整本书章级分析硬失败。
- [ ] 世界观空结构、人物完整小传全失败、profile 缺失均能被门禁识别。
- [ ] 大上下文预算配置支持 100 万上下文和阶段级大输出预算。
- [ ] 不修改 `docs/analysis/` 下历史事故报告，不修复历史素材 YAML，不执行 `nm storage sync` 到事故素材。

## 自检记录

- Spec coverage: 覆盖发布门禁、CLI 参数、sync 阻断、报告展示、大上下文预算、`pacing=None`、worldbuilding/characters/profile 阶段语义和历史事故只读回归。
- Placeholder scan: 已检查常见占位表达，正文没有未落地的占位步骤。
- Type consistency: 全部新增行为沿用 `RunStatus`、`StageResult`、`Diagnostic`、`ProgressCounts`；不新增状态枚举。
