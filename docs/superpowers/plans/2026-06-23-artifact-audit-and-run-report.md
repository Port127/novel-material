# 产物审计与运行报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不修改现有小说事实产物的前提下，为完整流水线增加确定性产物审计、预算受控的可疑项 LLM 复审、不可变机器报告、Markdown 报告和简洁终端摘要。

**Architecture:** `audit` 包只读取现有 YAML 并返回稳定的 `ArtifactAudit`，通过独立 reviewer 协议控制可选 LLM 复审；`reporting` 包只消费 `RunEvent` 与审计事件，构建并原子写入运行报告。Pipeline 继续以 `RunResult` 为唯一业务结论，`ReportSink` 作为 required sink 在 `RunCompleted` 时落盘，写入失败只能将原成功结果降级，不能反推或覆盖业务事实。

**Tech Stack:** Python 3.10+、Pydantic v2、Typer、Rich、PyYAML、contextvars、pytest。

---

> **跨会话执行入口：** 实际实施从 `docs/superpowers/execution/2026-06-23-artifact-audit-report/STATE.md` 开始。该目录把本计划拆为 14 个可独立恢复的 packet；新会话只读取当前 packet，不加载本文件全文。

## 实施边界

- 本计划只实施设计文档第一期“审计与报告”。前置导航与人物小传、分层世界观与作品画像分别另立实施计划。
- 不修改、清洗、迁移、补写或重跑 `data/novels/` 中任何已有事实 YAML；真实素材只作为只读验收证据。
- 不修改用户当前未提交的 `docs/feedback.md`。
- 最终审计必须只读；`--review` 只判断已有问题，不调用任何修复入口。
- 默认测试不得调用真实 LLM、embedding、PostgreSQL、storage sync 或数据库 migration。
- 测试全部使用 `tmp_path`、fake reviewer、`MemoryEventSink` 和 `RecordingTerminal`。
- `runtime`、`run_logging`、`terminal` 现有依赖边界继续生效；`run_logging` 与 `terminal` 不得互相 import。
- 报告不得包含原文、prompt、API Key、数据库凭据或未清理异常正文。
- `blocker` 必须阻止同步并得到 `failed`/退出码 1；`error` 得到 `degraded`/退出码 3；`warning` 与 `info` 不阻断。
- 每个 Task 先写失败测试并确认失败，再实现最小代码、运行定向与相关回归测试，最后按项目中文提交规范提交。

## 文件结构与职责

### 新建文件

```text
src/novel_material/audit/
├── __init__.py       # 对外导出 ArtifactAudit、ArtifactIssue、audit_material
├── models.py         # 审计等级、问题、检查结果与状态映射
├── rules.py          # 只读确定性规则，不负责终端或持久化
├── budget.py         # 可选 LLM 复审的时间/调用预算
├── reviewer.py       # reviewer 协议、NullReviewer 与 LLMArtifactReviewer
└── service.py        # 规则执行、复审选择、去重、排序和 StageResult 适配

src/novel_material/reporting/
├── __init__.py       # 对外导出报告构建、读取与写入入口
├── models.py         # 不可变报告 schema
├── builder.py        # RunEvent + ArtifactAudit → PipelineRunReport
├── markdown.py       # PipelineRunReport → Markdown
├── writer.py         # runs/latest 的原子写入与读取
└── sink.py           # required ReportSink，RunCompleted 时生成报告

src/novel_material/run_logging/
└── reader.py         # 按 run_id 读取和校验轮转 JSONL 事件

tests/audit/
├── test_models.py
├── test_rules.py
├── test_budget.py
├── test_reviewer.py
└── test_service.py

tests/reporting/
├── test_builder.py
├── test_markdown.py
├── test_writer.py
└── test_sink.py
```

### 修改文件

- `src/novel_material/runtime/context.py`：让当前运行上下文携带默认 dispatcher。
- `src/novel_material/runtime/summary.py`：补充调用次数、运行时间和阶段摘要聚合。
- `src/novel_material/infra/llm.py`：未显式传 dispatcher 时使用当前运行 dispatcher。
- `src/novel_material/pipeline/orchestrator.py`：发布带阶段名、耗时、计数和诊断的完成事件；未捕获异常转换为失败阶段。
- `src/novel_material/pipeline/stages.py`：新增只读审计阶段入口。
- `src/novel_material/cli/pipeline_common.py`：把 audit 放在 sync 前，并为 full/continue 构造日志与报告 sinks。
- `src/novel_material/cli/pipeline.py`：新增 `pipeline report`，并显示最终报告摘要。
- `src/novel_material/cli/validate.py`：新增 `validate artifacts [--review]`。
- `src/novel_material/infra/path_service.py`：增加报告目录和 latest/run 报告路径。
- `config/settings.yaml`：增加审计复审预算和报告 schema 配置。
- `tests/runtime/test_runtime_context.py`、`tests/runtime/test_runtime_summary.py`：覆盖 dispatcher 继承与新增聚合字段。
- `tests/pipeline/test_orchestrator.py`、`tests/cli/test_pipeline_contract.py`、`tests/cli/test_command_contracts.py`：覆盖审计阻断、报告降级、CLI 和退出码。
- `tests/run_logging/test_run_logging_core.py`：覆盖按 run_id 读取轮转事件。
- `tests/runtime/test_dependencies.py`：锁定 audit/reporting 依赖边界。
- `ARCHITECTURE.md`、`docs/USER_MANUAL.md`、`docs/README.md`、`docs/REQUIREMENTS.md`：同步第一期已实现行为。

## 设计规格覆盖与明确延期

本计划完整覆盖设计文档的审计条目、严重程度、只读混合审计、报告文件布局、终端摘要、失败状态、原子写入和第一期测试要求。

以下内容不属于本计划，必须由后续独立计划实现：

- `evaluation.yaml` 3.0.0、`--window` 解耦、5–12 名主要人物选择与完整小传：第二期。
- 分层世界观、实体关系、`work_profile.yaml`、存储和搜索适配：第三期。
- 跨素材章节规模基线，以及同 mode/provider/embedding provenance 的正式三次运行 10% 发布门禁：第二期在相关 provenance 字段稳定后实现。本期只计算同素材、同 command 的历史报告基线，无法比较时明确输出 unavailable。

这些延期项不得以空字段、占位命令或未生效开关出现在第一期“完成”声明中。

---

### Task 1：建立稳定审计契约

**Files:**
- Create: `src/novel_material/audit/__init__.py`
- Create: `src/novel_material/audit/models.py`
- Create: `tests/audit/test_models.py`

- [ ] **Step 1: 编写等级聚合与稳定序列化失败测试**

```python
from novel_material.audit.models import (
    ArtifactAudit,
    ArtifactIssue,
    AuditSeverity,
    audit_run_status,
)
from novel_material.runtime.contracts import RunStatus


def issue(code: str, severity: AuditSeverity) -> ArtifactIssue:
    return ArtifactIssue(
        code=code,
        severity=severity,
        artifact="characters/profiles/主角.yaml",
        message="档案不完整",
        evidence={"missing_fields": ["arc_summary"]},
        next_actions=("nm pipeline characters nm_demo --repair-character 主角",),
    )


def test_audit_status_maps_blocker_error_and_warning():
    assert audit_run_status(ArtifactAudit(material_id="nm_demo")) is RunStatus.SUCCESS
    assert audit_run_status(
        ArtifactAudit(material_id="nm_demo", issues=(issue("sparse", AuditSeverity.WARNING),))
    ) is RunStatus.SUCCESS
    assert audit_run_status(
        ArtifactAudit(material_id="nm_demo", issues=(issue("fallback", AuditSeverity.ERROR),))
    ) is RunStatus.DEGRADED
    assert audit_run_status(
        ArtifactAudit(material_id="nm_demo", issues=(issue("missing", AuditSeverity.BLOCKER),))
    ) is RunStatus.FAILED


def test_audit_dump_is_stable_and_contains_summary_counts():
    audit = ArtifactAudit(
        material_id="nm_demo",
        checks=("required_files", "characters"),
        issues=(
            issue("fallback", AuditSeverity.ERROR),
            issue("sparse", AuditSeverity.WARNING),
        ),
    )
    payload = audit.model_dump(mode="json")
    assert payload["schema_version"] == 1
    assert payload["summary"] == {
        "blocker": 0,
        "error": 1,
        "warning": 1,
        "info": 0,
        "not_reviewed_due_to_budget": 0,
    }
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/audit/test_models.py -v`

Expected: FAIL，提示 `novel_material.audit` 不存在。

- [ ] **Step 3: 实现不可变审计模型与状态映射**

```python
# src/novel_material/audit/models.py
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field

from novel_material.runtime.contracts import RunStatus


class AuditSeverity(str, Enum):
    BLOCKER = "blocker"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReviewState(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    NOT_REVIEWED_DUE_TO_BUDGET = "not_reviewed_due_to_budget"


class ArtifactIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    severity: AuditSeverity
    artifact: str = Field(min_length=1)
    message: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    next_actions: tuple[str, ...] = ()
    reviewable: bool = False
    review_state: ReviewState = ReviewState.NOT_REQUIRED


class ReviewBudgetUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str = "rules_only"
    max_seconds: float = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)
    max_calls: int = Field(default=0, ge=0)
    calls_used: int = Field(default=0, ge=0)
    stop_reason: str | None = None


class ArtifactAudit(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    material_id: str = Field(min_length=1)
    checks: tuple[str, ...] = ()
    issues: tuple[ArtifactIssue, ...] = ()
    review_budget: ReviewBudgetUsage = Field(default_factory=ReviewBudgetUsage)

    @computed_field
    @property
    def summary(self) -> dict[str, int]:
        counts = {severity.value: 0 for severity in AuditSeverity}
        counts[ReviewState.NOT_REVIEWED_DUE_TO_BUDGET.value] = 0
        for item in self.issues:
            counts[item.severity.value] += 1
            if item.review_state is ReviewState.NOT_REVIEWED_DUE_TO_BUDGET:
                counts[ReviewState.NOT_REVIEWED_DUE_TO_BUDGET.value] += 1
        return counts


def audit_run_status(audit: ArtifactAudit) -> RunStatus:
    severities = {item.severity for item in audit.issues}
    if AuditSeverity.BLOCKER in severities:
        return RunStatus.FAILED
    if AuditSeverity.ERROR in severities:
        return RunStatus.DEGRADED
    return RunStatus.SUCCESS
```

`audit/__init__.py` 在本 Task 只导出上述模型；Task 3 增加服务导出。模块导入不得触发文件读取。

- [ ] **Step 4: 运行定向测试**

Run: `python -m pytest tests/audit/test_models.py -v`

Expected: 2 passed。

- [ ] **Step 5: 提交审计契约**

```bash
git add src/novel_material/audit tests/audit/test_models.py
git commit -m "feat(audit): 建立产物审计结果契约" -m "主要改动：
- 增加审计严重程度、复审状态、问题条目和汇总模型
- 固化 blocker、error 与运行状态的映射

验证结果：
- python -m pytest tests/audit/test_models.py -v，通过"
```

### Task 2：实现当前产物的确定性只读规则

**Files:**
- Create: `src/novel_material/audit/rules.py`
- Create: `tests/audit/test_rules.py`

- [ ] **Step 1: 编写缺失事实文件与人物兜底失败测试**

```python
from pathlib import Path

import yaml

from novel_material.audit.models import AuditSeverity
from novel_material.audit.rules import AuditContext, run_deterministic_rules


def write_yaml(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")


def test_missing_core_fact_files_are_blockers(tmp_path):
    issues = run_deterministic_rules(AuditContext("nm_demo", tmp_path / "nm_demo"))
    assert {item.code for item in issues} == {
        "meta_missing",
        "chapter_index_missing",
        "chapters_missing",
    }
    assert {item.severity for item in issues} == {AuditSeverity.BLOCKER}


def test_major_character_statistical_fallback_is_error(tmp_path):
    novel = tmp_path / "nm_demo"
    write_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "status": "finalized"})
    write_yaml(novel / "chapter_index.yaml", [{"chapter": 1}])
    write_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "足够长的章节摘要" * 5}])
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
```

- [ ] **Step 2: 编写覆盖率、世界观空结构与旧格式证据提示测试**

```python
def test_coverage_worldbuilding_and_legacy_evidence_are_reported(tmp_path):
    novel = tmp_path / "nm_demo"
    write_yaml(novel / "meta.yaml", {"material_id": "nm_demo", "status": "finalized"})
    write_yaml(novel / "chapter_index.yaml", [{"chapter": 1}, {"chapter": 2}])
    write_yaml(novel / "chapters.yaml", [{"chapter": 1, "summary": "摘要" * 30}])
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

    assert by_code["chapter_coverage_incomplete"].severity is AuditSeverity.BLOCKER
    assert by_code["worldbuilding_empty"].severity is AuditSeverity.ERROR
    assert by_code["worldbuilding_legacy_without_evidence"].severity is AuditSeverity.WARNING
    assert by_code["worldbuilding_legacy_without_evidence"].reviewable is True
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/audit/test_rules.py -v`

Expected: FAIL，提示 `novel_material.audit.rules` 不存在。

- [ ] **Step 4: 实现规则上下文和六组纯函数规则**

`rules.py` 定义：

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from novel_material.infra.yaml_io import load_yaml, load_yaml_list

from .models import ArtifactIssue, AuditSeverity, ReviewState


@dataclass(frozen=True)
class AuditContext:
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
    return ArtifactIssue(
        code=code,
        severity=severity,
        artifact=artifact,
        message=message,
        evidence=evidence or {},
        next_actions=next_actions,
        reviewable=reviewable,
        review_state=ReviewState.PENDING if reviewable else ReviewState.NOT_REQUIRED,
    )
```

实现并注册以下规则，所有规则只读取 `context.novel_dir`：

1. `check_required_files`：`meta.yaml`、`chapter_index.yaml`、`chapters.yaml` 缺失分别产生 blocker。
2. `check_chapter_coverage`：用章节号集合比较 index 与 chapters；缺章产生 `chapter_coverage_incomplete` blocker，evidence 写 `expected/actual/missing_chapters`，缺章列表最多保留 50 个并另写总数。
3. `check_character_profiles`：遍历 `characters/profiles/*.yaml`；`role in {protagonist, antagonist}` 且描述匹配统计模板或 `arc_summary/psychology/relationships` 为空时产生 `character_profile_fallback` error。supporting 同类问题产生 warning；minor 不检查完整小传字段。
4. `check_worldbuilding`：读取 `_index.yaml`；`llm_success` 为假且四类计数全零产生 `worldbuilding_empty` error。只存在旧四文件结构时产生可复审 warning `worldbuilding_legacy_without_evidence`，不因力量等级为零单独报错。
5. `check_finalized_artifacts`：仅当 `meta.status == finalized` 时检查 outline、characters、worldbuilding、tags 的入口文件；缺失产生 error，不把旧未 finalized 素材误判为失败。
6. `check_insight_coverage`：`chapter_insights/` 不存在时产生 info；存在时按普通章节号比较，缺失产生 warning，失败占位文件计入已处理但另产生 warning。

最后定义：

```python
RULES: tuple[tuple[str, AuditRule], ...] = (
    ("required_files", check_required_files),
    ("chapter_coverage", check_chapter_coverage),
    ("characters", check_character_profiles),
    ("worldbuilding", check_worldbuilding),
    ("finalized_artifacts", check_finalized_artifacts),
    ("insight_coverage", check_insight_coverage),
)


def run_deterministic_rules(context: AuditContext) -> tuple[ArtifactIssue, ...]:
    issues = [item for _name, rule in RULES for item in rule(context)]
    return tuple(sorted(issues, key=lambda item: (item.severity.value, item.code, item.artifact)))
```

- [ ] **Step 5: 运行规则测试**

Run: `python -m pytest tests/audit/test_rules.py -v`

Expected: 3 passed。

- [ ] **Step 6: 提交确定性规则**

```bash
git add src/novel_material/audit/rules.py tests/audit/test_rules.py
git commit -m "feat(audit): 增加现有产物确定性检查" -m "主要改动：
- 检查核心文件、章节覆盖、人物兜底、世界观空结构和 finalized 产物
- 对旧世界观证据缺失和 insight 覆盖输出非阻断问题
- 所有规则保持只读并返回结构化证据

验证结果：
- python -m pytest tests/audit/test_rules.py -v，通过"
```

### Task 3：实现审计服务、阶段结果与规则 CLI

**Files:**
- Create: `src/novel_material/audit/service.py`
- Modify: `src/novel_material/audit/__init__.py`
- Modify: `src/novel_material/pipeline/stages.py`
- Modify: `src/novel_material/cli/validate.py`
- Create: `tests/audit/test_service.py`
- Modify: `tests/cli/test_command_contracts.py`

- [ ] **Step 1: 编写去重、排序和 StageResult 映射失败测试**

```python
from novel_material.audit.models import ArtifactIssue, AuditSeverity
from novel_material.audit.service import audit_material, audit_to_stage_result
from novel_material.runtime.contracts import RunStatus


def test_audit_service_deduplicates_same_issue(tmp_path, monkeypatch):
    duplicate = ArtifactIssue(
        code="same",
        severity=AuditSeverity.WARNING,
        artifact="tags.yaml",
        message="重复问题",
    )
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("one", lambda _ctx: (duplicate,)), ("two", lambda _ctx: (duplicate,))),
    )
    audit = audit_material("nm_demo", novels_dir=tmp_path)
    assert audit.checks == ("one", "two")
    assert audit.issues == (duplicate,)


def test_audit_error_maps_to_degraded_stage(tmp_path, monkeypatch):
    problem = ArtifactIssue(
        code="fallback",
        severity=AuditSeverity.ERROR,
        artifact="characters/profiles/主角.yaml",
        message="主要人物为空壳",
    )
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("characters", lambda _ctx: (problem,)),),
    )
    stage = audit_to_stage_result(audit_material("nm_demo", novels_dir=tmp_path))
    assert stage.name == "audit"
    assert stage.status is RunStatus.DEGRADED
    assert stage.outputs["audit"]["summary"]["error"] == 1
```

- [ ] **Step 2: 编写 CLI 退出码失败测试**

```python
def test_validate_artifacts_uses_audit_status(monkeypatch):
    from novel_material.audit.models import ArtifactAudit, ArtifactIssue, AuditSeverity

    monkeypatch.setattr(
        "novel_material.cli.validate.audit_material",
        lambda *_args, **_kwargs: ArtifactAudit(
            material_id="nm_demo",
            issues=(ArtifactIssue(
                code="fallback",
                severity=AuditSeverity.ERROR,
                artifact="characters/profiles/主角.yaml",
                message="主要人物为空壳",
            ),),
        ),
    )
    result = runner.invoke(app, ["validate", "artifacts", "nm_demo"])
    assert result.exit_code == 3
    assert "fallback" in result.stderr
    assert "规则审计" in result.stderr
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/audit/test_service.py tests/cli/test_command_contracts.py::test_validate_artifacts_uses_audit_status -v`

Expected: FAIL，提示 service 或 `artifacts` 命令不存在。

- [ ] **Step 4: 实现服务和 StageResult 适配**

`audit_material(material_id, *, novels_dir=NOVELS_DIR)` 逐条执行 `RULES`，以 `(code, artifact, message)` 去重，按 `blocker > error > warning > info`、code、artifact 排序。本 Task 只提供完整可用的规则审计；Task 4 在保持默认行为不变的前提下扩展 reviewer 与 budget 参数。

`audit_to_stage_result()` 使用 `audit_run_status()`，counts 的 expected/processed 都等于检查数，diagnostics 为每个 blocker/error 建立稳定 code，outputs 保存 `audit.model_dump(mode="json")`。本 Task 的阶段入口保持纯返回值：

```python
def run_artifact_audit_stage(material_id: str, **kwargs) -> StageResult:
    audit = audit_material(material_id, **kwargs)
    return audit_to_stage_result(audit)
```

- [ ] **Step 5: 实现 `nm validate artifacts` 规则模式**

在 `cli/validate.py` 注册：

```python
@app.command("artifacts")
def cmd_validate_artifacts(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    audit = audit_material(material_id)
    for item in audit.issues:
        typer.echo(f"{item.severity.value}: {item.code}: {item.message}", err=True)
    status = audit_run_status(audit)
    typer.echo(f"规则审计完成：{audit.summary}", err=status is not RunStatus.SUCCESS)
    if status is not RunStatus.SUCCESS:
        raise typer.Exit(int(exit_code_for(status)))
```

- [ ] **Step 6: 运行定向与现有 CLI 回归**

Run: `python -m pytest tests/audit/test_service.py tests/cli/test_command_contracts.py tests/validation -v`

Expected: 全部通过。

- [ ] **Step 7: 提交审计服务与 CLI**

```bash
git add src/novel_material/audit src/novel_material/pipeline/stages.py src/novel_material/cli/validate.py tests/audit/test_service.py tests/cli/test_command_contracts.py
git commit -m "feat(audit): 接入产物审计服务与命令" -m "主要改动：
- 统一审计问题去重、排序和阶段状态转换
- 增加 nm validate artifacts 规则审计入口
- 保持审计只读并使用稳定退出码

验证结果：
- python -m pytest tests/audit/test_service.py tests/cli/test_command_contracts.py tests/validation -v，通过"
```

### Task 4：增加预算受控的可疑项 LLM 复审

**Files:**
- Create: `src/novel_material/audit/budget.py`
- Create: `src/novel_material/audit/reviewer.py`
- Modify: `src/novel_material/audit/service.py`
- Create: `tests/audit/test_budget.py`
- Create: `tests/audit/test_reviewer.py`
- Modify: `src/novel_material/cli/validate.py`
- Modify: `tests/cli/test_command_contracts.py`
- Modify: `config/settings.yaml`

- [ ] **Step 1: 编写预算停止失败测试**

```python
from novel_material.audit.budget import ReviewBudget
from novel_material.runtime.testing import FakeClock


def test_budget_refuses_call_that_would_cross_deadline():
    clock = FakeClock()
    budget = ReviewBudget(max_seconds=100, max_calls=2, clock=clock.monotonic)
    assert budget.reserve(estimated_seconds=60) is True
    clock.advance(50)
    assert budget.reserve(estimated_seconds=60) is False
    assert budget.stop_reason == "time_budget_exhausted"


def test_budget_refuses_calls_after_call_limit():
    budget = ReviewBudget(max_seconds=1000, max_calls=1, clock=lambda: 0)
    assert budget.reserve(estimated_seconds=10) is True
    assert budget.reserve(estimated_seconds=10) is False
    assert budget.stop_reason == "call_budget_exhausted"
```

- [ ] **Step 2: 编写 fake reviewer 与只读复审失败测试**

```python
from novel_material.audit.models import ReviewState
from novel_material.audit.reviewer import ReviewDecision


class FakeReviewer:
    def __init__(self):
        self.calls = []

    def review(self, issue, evidence_excerpt):
        self.calls.append((issue.code, evidence_excerpt))
        return ReviewDecision(
            code=issue.code,
            confirmed=True,
            rationale="证据不足，保留警告",
        )


def test_service_reviews_only_reviewable_issues_and_never_writes_yaml(tmp_path, monkeypatch):
    novel = tmp_path / "nm_demo"
    novel.mkdir()
    source = novel / "worldbuilding/_index.yaml"
    source.parent.mkdir()
    source.write_text("llm_success: true\n", encoding="utf-8")
    before = source.read_bytes()
    reviewer = FakeReviewer()

    audit = audit_material(
        "nm_demo",
        novels_dir=tmp_path,
        reviewer=reviewer,
        budget=ReviewBudget(max_seconds=100, max_calls=1, clock=lambda: 0),
    )

    assert len(reviewer.calls) <= 1
    assert source.read_bytes() == before
    assert all(
        item.review_state in {
            ReviewState.NOT_REQUIRED,
            ReviewState.CONFIRMED,
            ReviewState.NOT_REVIEWED_DUE_TO_BUDGET,
        }
        for item in audit.issues
    )
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/audit/test_budget.py tests/audit/test_reviewer.py -v`

Expected: FAIL，提示 budget/reviewer 模块不存在。

- [ ] **Step 4: 实现预算和 reviewer 协议**

`budget.py` 实现不可回退的 `ReviewBudget`：首次 reserve 记录起点；每次 reserve 同时检查 `calls_used < max_calls` 和 `elapsed + estimated_seconds <= max_seconds`。拒绝后固定 `stop_reason`，后续 reserve 始终返回 False。`snapshot(mode)` 返回 `ReviewBudgetUsage`，供 ArtifactAudit 和最终报告记录预算上限、实际耗时、调用数及停止原因。

`reviewer.py` 定义：

```python
class ReviewDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    confirmed: bool
    rationale: str = Field(min_length=1, max_length=500)


class ArtifactReviewer(Protocol):
    def review(self, issue: ArtifactIssue, evidence_excerpt: str) -> ReviewDecision: ...
```

`LLMArtifactReviewer` 只发送问题 code、message、结构化 evidence 和最多 4000 字符的对应 YAML 摘录，要求返回 `code/confirmed/rationale` JSON。使用 `call_llm()`、`load_config()` 和 `LLM_OTHER_TIMEOUT`；不提供任何“修复”工具或写文件引用。解析失败产生 `review_failed` warning，不提升原问题严重程度。

- [ ] **Step 5: 将复审接入审计服务**

service 只选择 `reviewable=True` 且 `review_state=PENDING` 的问题。每次调用前以配置 `ARTIFACT_REVIEW_ESTIMATED_CALL_SECONDS` reserve；预算拒绝后，把剩余可复审问题复制为 `NOT_REVIEWED_DUE_TO_BUDGET`。confirmed 保留问题并写 rationale；dismissed 保留条目但降为 info、状态为 `DISMISSED`，保证人工审计可追溯。

规则模式写入 `ReviewBudgetUsage(mode="rules_only")`；复审模式在返回前写入 `budget.snapshot(mode="llm_review")`。预算信息必须进入 `audit.model_dump(mode="json")`，不得只存在于终端文本。

把 `audit_material()` 扩展为：

```python
def audit_material(
    material_id: str,
    *,
    novels_dir: Path = NOVELS_DIR,
    reviewer: ArtifactReviewer | None = None,
    budget: ReviewBudget | None = None,
) -> ArtifactAudit:
```

只有 reviewer 和 budget 同时存在时才复审；缺少任一参数时保持 Task 3 的规则模式。

在 `cli/validate.py` 为 `artifacts` 增加 `--review`。未传参数时调用规则模式；传入时根据配置创建 `LLMArtifactReviewer` 与 `ReviewBudget`，不得复用或改写任何事实 YAML。补充 CLI 测试：默认模式 fake `call_llm` 若被调用立即失败；`--review` 模式注入 FakeReviewer 并验证只复审 reviewable 问题。

在 `config/settings.yaml` 增加：

```yaml
ARTIFACT_REVIEW_TIME_FRACTION_STANDARD: 0.10
ARTIFACT_REVIEW_MAX_CALLS_STANDARD: 3
ARTIFACT_REVIEW_MAX_CALLS_DEEP: 10
ARTIFACT_REVIEW_ESTIMATED_CALL_SECONDS: 120
ARTIFACT_REVIEW_EVIDENCE_CHARS: 4000
```

- [ ] **Step 6: 运行审计测试与无真实 LLM 回归**

Run: `python -m pytest tests/audit -v`

Expected: 全部通过；测试输出不包含网络请求。

- [ ] **Step 7: 提交受控复审**

```bash
git add src/novel_material/audit src/novel_material/cli/validate.py config/settings.yaml tests/audit tests/cli/test_command_contracts.py
git commit -m "feat(audit): 增加预算受控的可疑项复审" -m "主要改动：
- 增加时间与调用次数双重预算
- 只向 reviewer 提供受限结构化证据并保持最终审计只读
- 明确确认、驳回、复审失败和预算停止状态

验证结果：
- python -m pytest tests/audit -v，通过且未调用真实 LLM"
```

### Task 5：让运行事件完整覆盖嵌套 LLM 与阶段结果

**Files:**
- Modify: `src/novel_material/runtime/context.py`
- Modify: `src/novel_material/runtime/summary.py`
- Modify: `src/novel_material/infra/llm.py`
- Modify: `src/novel_material/pipeline/orchestrator.py`
- Modify: `src/novel_material/pipeline/stages.py`
- Modify: `tests/runtime/test_runtime_context.py`
- Modify: `tests/runtime/test_runtime_summary.py`
- Modify: `tests/pipeline/test_orchestrator.py`

- [ ] **Step 1: 编写默认 dispatcher 继承失败测试**

```python
from novel_material.runtime.context import current_dispatcher, run_context, stage_context
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.runtime.testing import MemoryEventSink


def test_stage_context_inherits_run_dispatcher():
    sink = MemoryEventSink()
    dispatcher = RuntimeDispatcher([sink])
    with run_context("pipeline full", "nm_demo", run_id="run-1", dispatcher=dispatcher):
        with stage_context("analyze"):
            assert current_dispatcher() is dispatcher
    assert current_dispatcher() is None
```

- [ ] **Step 2: 编写阶段耗时、计数和异常转换失败测试**

```python
def test_stage_completed_event_contains_name_duration_counts_and_diagnostics():
    sink = MemoryEventSink()
    result = PipelineOrchestrator(
        [spec("analyze", RunStatus.DEGRADED)],
        dispatcher=RuntimeDispatcher([sink]),
    ).run(request())
    completed = sink.events_named("StageCompleted")[0]
    assert completed.attributes["stage_name"] == "analyze"
    assert completed.attributes["counts"] == result.stages[0].counts.model_dump(mode="json")
    assert completed.attributes["diagnostics"] == []
    assert completed.duration_ms is not None


def test_unhandled_stage_exception_becomes_failed_result_and_run_completed_event():
    sink = MemoryEventSink()
    broken = StageSpec(
        "analyze",
        lambda _request: (_ for _ in ()).throw(ValueError("bad payload")),
        blocking=True,
    )
    result = PipelineOrchestrator(
        [broken],
        dispatcher=RuntimeDispatcher([sink]),
    ).run(request())
    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "stage_unhandled_exception"
    assert sink.events_named("RunCompleted")
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/runtime/test_runtime_context.py tests/runtime/test_runtime_summary.py tests/pipeline/test_orchestrator.py -v`

Expected: FAIL，提示 `current_dispatcher` 不存在、StageCompleted 属性缺失或 ValueError 外抛。

- [ ] **Step 4: 实现运行 dispatcher 上下文**

`RuntimeContext` 不直接保存 dispatcher，避免把服务对象序列化。新增独立 `ContextVar[RuntimeDispatcher | None]`；`run_context(..., dispatcher=None)` 同时 set/reset 两个 token，`stage_context` 和 `request_context` 自动继承。导出 `current_dispatcher()`。

`call_llm()` 将：

```python
event_dispatcher = dispatcher or current_dispatcher() or NullDispatcher()
```

替换当前只使用显式 dispatcher 的逻辑。保留显式参数最高优先级。

OperationCompleted.attributes 增加 `estimated_cost`：按本次实际 input/output tokens 与当前 provider 的 `config["llm"]["pricing"]` 计算；usage 缺失时写 `None`，不得用零冒充可获得成本。

- [ ] **Step 5: 丰富 orchestrator 事件并捕获普通异常**

为 `PipelineOrchestrator` 注入 `clock: Callable[[], float] = time.monotonic`。执行阶段前记录起点；阶段返回后用外层实测耗时覆盖 `duration_ms`。捕获 `Exception`，生成 failed StageResult：

```python
Diagnostic(
    code="stage_unhandled_exception",
    message=f"阶段 {spec.name} 未处理异常: {type(exc).__name__}",
    severity="error",
    retryable=True,
)
```

不得把异常正文写入 message。`StageCompleted` 事件写 `stage_name/counts/diagnostics`，`RunStarted` 写 `request.options.report_prior_stages` 的摘要，`RunCompleted` 写最终 counts 和 diagnostics。`RunRequest` 新增可空 `started_at`；full 在 ingest 前记录时间并传入，使 RunStarted 的 occurred_at 覆盖完整运行。所有属性先使用 `model_dump(mode="json")`。

- [ ] **Step 6: 扩展 RunSummaryAccumulator**

新增并测试以下字段：`started_at`、`completed_at`、`operation_attempts`、`operation_completed`、`estimated_cost`、`stage_durations_ms`、`stage_statuses`。`consume()` 按 `event_id` 去重；OperationStarted 增加尝试数，OperationCompleted 增加完成数、tokens 和可用成本；任一成本不可获得时 snapshot 的 estimated_cost 为 None，避免不完整成本被误认为完整。StageCompleted 使用 `stage_name` 聚合；RunStarted/RunCompleted 记录时间。保留现有字段和测试兼容。

- [ ] **Step 7: 发布独立审计完成事件**

在 `pipeline/stages.py` 的 `run_artifact_audit_stage()` 中，得到 ArtifactAudit 后通过 `current_dispatcher()` 发布 `ArtifactAuditCompleted`，attributes 只包含 `audit.model_dump(mode="json")`。没有运行 dispatcher 的独立库调用不发布事件，仍正常返回 StageResult。事件使用当前 run/stage/material context，不把领域载荷放入通用 StageCompleted。

```python
def run_artifact_audit_stage(material_id: str, **kwargs) -> StageResult:
    audit = audit_material(material_id, **kwargs)
    dispatcher = current_dispatcher()
    context = current_context()
    if dispatcher is not None and context is not None:
        now = datetime.now(timezone.utc)
        dispatcher.emit(RunEvent(
            event_name="ArtifactAuditCompleted",
            event_id=new_id("event"),
            occurred_at=now,
            observed_at=now,
            run_id=context.run_id,
            stage_id=context.stage_id,
            command=context.command,
            component="audit",
            operation="validate_artifacts",
            material_id=context.material_id,
            status=audit_run_status(audit),
            attributes={"audit": audit.model_dump(mode="json")},
        ))
    return audit_to_stage_result(audit)
```

- [ ] **Step 8: 运行 runtime、LLM telemetry 和 pipeline 回归**

Run: `python -m pytest tests/runtime tests/infra/test_llm_telemetry.py tests/pipeline/test_orchestrator.py -v`

Expected: 全部通过。

- [ ] **Step 9: 提交事件链路增强**

```bash
git add src/novel_material/runtime src/novel_material/infra/llm.py src/novel_material/pipeline/orchestrator.py src/novel_material/pipeline/stages.py tests/runtime tests/infra/test_llm_telemetry.py tests/pipeline/test_orchestrator.py
git commit -m "feat(runtime): 补齐报告所需运行事件" -m "主要改动：
- 让嵌套 LLM 调用继承当前运行 dispatcher
- 在阶段完成事件中记录名称、耗时、计数和诊断
- 将未处理阶段异常转换为稳定失败结果并继续发布完成事件

验证结果：
- python -m pytest tests/runtime tests/infra/test_llm_telemetry.py tests/pipeline/test_orchestrator.py -v，通过"
```

### Task 6：构建机器报告模型与事件聚合器

**Files:**
- Create: `src/novel_material/reporting/__init__.py`
- Create: `src/novel_material/reporting/models.py`
- Create: `src/novel_material/reporting/builder.py`
- Create: `tests/reporting/test_builder.py`

- [ ] **Step 1: 编写完整报告构建失败测试**

```python
from datetime import datetime, timedelta, timezone

from novel_material.reporting.builder import build_run_report
from novel_material.runtime.testing import event


def test_builder_combines_runtime_and_artifact_quality():
    started = datetime(2026, 6, 23, 1, 0, tzinfo=timezone.utc)
    audit = {
        "schema_version": 1,
        "material_id": "nm_demo",
        "checks": ["characters"],
        "issues": [{
            "code": "character_profile_fallback",
            "severity": "error",
            "artifact": "characters/profiles/主角.yaml",
            "message": "主要人物为空壳",
            "evidence": {},
            "next_actions": ["nm pipeline characters nm_demo --repair-character 主角"],
            "reviewable": False,
            "review_state": "not_required",
        }],
    }
    events = [
        event("RunStarted", occurred_at=started, material_id="nm_demo"),
        event(
            "StageCompleted",
            occurred_at=started + timedelta(seconds=10),
            stage_id="stage-audit",
            status="degraded",
            duration_ms=10000,
            attributes={"stage_name": "audit", "counts": {}, "diagnostics": []},
        ),
        event(
            "ArtifactAuditCompleted",
            occurred_at=started + timedelta(seconds=10),
            stage_id="stage-audit",
            status="degraded",
            attributes={"audit": audit},
        ),
        event(
            "OperationCompleted",
            occurred_at=started + timedelta(seconds=11),
            attributes={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        ),
        event(
            "RunCompleted",
            occurred_at=started + timedelta(seconds=20),
            material_id="nm_demo",
            status="degraded",
            attributes={"counts": {}, "diagnostics": []},
        ),
    ]

    report = build_run_report(events)

    assert report.run_id == "run-test"
    assert report.material_id == "nm_demo"
    assert report.status.value == "degraded"
    assert report.duration_ms == 20000
    assert report.runtime.total_tokens == 150
    assert report.artifact_quality.summary.error == 1
    assert report.next_actions == (
        "nm pipeline characters nm_demo --repair-character 主角",
    )
```

- [ ] **Step 2: 编写事件不完整失败测试**

```python
import pytest

from novel_material.reporting.builder import ReportBuildError, build_run_report


def test_builder_rejects_missing_run_boundaries():
    with pytest.raises(ReportBuildError, match="RunStarted"):
        build_run_report([])
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/reporting/test_builder.py -v`

Expected: FAIL，提示 `novel_material.reporting` 不存在。

- [ ] **Step 4: 实现报告模型**

`models.py` 定义不可变模型：

```python
class SeverityCounts(BaseModel):
    model_config = ConfigDict(frozen=True)
    blocker: int = Field(default=0, ge=0)
    error: int = Field(default=0, ge=0)
    warning: int = Field(default=0, ge=0)
    info: int = Field(default=0, ge=0)
    not_reviewed_due_to_budget: int = Field(default=0, ge=0)


class RuntimeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    operation_attempts: int = Field(default=0, ge=0)
    operation_completed: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost: float | None = Field(default=None, ge=0)
    diagnostic_counts: dict[str, int] = Field(default_factory=dict)


class StageReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    status: RunStatus
    duration_ms: float = Field(ge=0)
    counts: dict = Field(default_factory=dict)
    diagnostic_codes: tuple[str, ...] = ()


class ArtifactQualityReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    checks: tuple[str, ...] = ()
    summary: SeverityCounts = Field(default_factory=SeverityCounts)
    issues: tuple[ArtifactIssue, ...] = ()
    review_budget: ReviewBudgetUsage = Field(default_factory=ReviewBudgetUsage)


class BaselineComparison(BaseModel):
    model_config = ConfigDict(frozen=True)
    kind: str = "unavailable"
    baseline_duration_ms: float | None = Field(default=None, ge=0)
    delta_percent: float | None = None


class PipelineRunReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = 1
    run_id: str
    material_id: str
    command: str
    status: RunStatus
    started_at: datetime
    completed_at: datetime
    duration_ms: float = Field(ge=0)
    stages: tuple[StageReport, ...] = ()
    runtime: RuntimeMetrics = Field(default_factory=RuntimeMetrics)
    artifact_quality: ArtifactQualityReport = Field(default_factory=ArtifactQualityReport)
    baseline: BaselineComparison = Field(default_factory=BaselineComparison)
    next_actions: tuple[str, ...] = ()
```

- [ ] **Step 5: 实现事件构建器**

`build_run_report(events, *, baseline_reports=())` 按 event_id 去重并按 `occurred_at` 排序；必须恰有同 run_id 的 RunStarted 和至少一个 RunCompleted。使用最后一个 RunCompleted 作为终态，RunStarted 中的 `report_prior_stages` 与 StageCompleted 共同构建阶段列表，OperationStarted/OperationCompleted 分别汇总尝试数和完成数、tokens 与成本，DiagnosticRaised 汇总代码。审计数据只从 `ArtifactAuditCompleted.attributes.audit` 读取并经 `ArtifactAudit.model_validate()` 校验。next actions 以问题顺序稳定去重；没有审计事件时 artifact_quality 为空，并增加 `audit_missing` 诊断计数。

baseline_reports 只选择同 material_id、同 command 且 status=success 的历史报告，以最近三次 duration 中位数计算 delta；不足一次时 `BaselineComparison.kind="unavailable"`。跨素材章节规模基线等第二期能够稳定记录 mode/provider/embedding provenance 后再实现，本期不得用不可比数据给出百分比。

- [ ] **Step 6: 运行构建器测试**

Run: `python -m pytest tests/reporting/test_builder.py tests/runtime/test_runtime_summary.py -v`

Expected: 全部通过。

- [ ] **Step 7: 提交报告模型与构建器**

```bash
git add src/novel_material/reporting tests/reporting/test_builder.py
git commit -m "feat(report): 建立运行与产物质量报告模型" -m "主要改动：
- 定义运行指标、阶段结果、产物质量和最终报告 schema
- 从去重运行事件构建稳定报告并校验审计载荷
- 汇总下一步命令且拒绝缺失运行边界的事件集

验证结果：
- python -m pytest tests/reporting/test_builder.py tests/runtime/test_runtime_summary.py -v，通过"
```

### Task 7：实现 Markdown、原子写入、ReportSink 与事件重读

**Files:**
- Create: `src/novel_material/reporting/markdown.py`
- Create: `src/novel_material/reporting/writer.py`
- Create: `src/novel_material/reporting/sink.py`
- Create: `src/novel_material/run_logging/reader.py`
- Create: `tests/reporting/test_markdown.py`
- Create: `tests/reporting/test_writer.py`
- Create: `tests/reporting/test_sink.py`
- Modify: `tests/run_logging/test_run_logging_core.py`
- Modify: `src/novel_material/infra/path_service.py`

- [ ] **Step 1: 编写 Markdown 与原子文件布局失败测试**

```python
def test_markdown_contains_conclusion_risks_and_next_actions(sample_report):
    text = render_markdown(sample_report)
    assert "# 运行与产物质量报告" in text
    assert "状态：degraded" in text
    assert "character_profile_fallback" in text
    assert "nm pipeline characters" in text
    assert "API Key" not in text


def test_writer_creates_immutable_run_and_atomic_latest_files(tmp_path, sample_report):
    writer = ReportWriter(tmp_path / "nm_demo")
    paths = writer.write(sample_report)
    assert paths.run_yaml == tmp_path / "nm_demo/reports/runs/run-test.yaml"
    assert paths.latest_yaml.read_text(encoding="utf-8") == paths.run_yaml.read_text(encoding="utf-8")
    assert paths.latest_markdown.exists()
    assert not list((tmp_path / "nm_demo/reports").rglob("*.tmp"))
```

- [ ] **Step 2: 编写 sink 故障与轮转事件读取失败测试**

```python
def test_report_sink_writes_on_run_completed(tmp_path, sample_events):
    sink = ReportSink(tmp_path / "nm_demo")
    for item in sample_events:
        sink.emit(item)
    assert (tmp_path / "nm_demo/reports/latest.yaml").exists()


def test_reader_merges_rotated_files_and_filters_run_id(tmp_path):
    first = tmp_path / "2026-06-23/pipeline_run-1.jsonl"
    second = tmp_path / "2026-06-23/pipeline_run-1.1.jsonl"
    other = tmp_path / "2026-06-23/pipeline_run-2.jsonl"
    for path, events in (
        (first, [event("RunStarted", run_id="run-1")]),
        (second, [event("RunCompleted", run_id="run-1", status="success")]),
        (other, [event("RunStarted", run_id="run-2")]),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(serialize_event(item) + "\n" for item in events), encoding="utf-8")
    loaded = read_run_events(tmp_path, "run-1")
    assert [item.event_name for item in loaded] == ["RunStarted", "RunCompleted"]
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/reporting tests/run_logging/test_run_logging_core.py -v`

Expected: FAIL，提示 markdown/writer/sink/reader 不存在。

- [ ] **Step 4: 实现确定性 Markdown 渲染**

`render_markdown(report)` 固定输出：结论、耗时与同素材基线（不可用时明确写“无可比基线”）、API 尝试/完成数、Token 与可用成本、阶段表、产物质量汇总、复审预算、按 blocker/error/warning/info 排序的问题、未复审项和下一步命令。动态值先转普通字符串，不启用 Rich markup；问题 message/evidence 经现有 `sanitize_value` 清理后再渲染。

- [ ] **Step 5: 实现原子报告写入**

`ReportWriter.write(report)`：

1. `reports/runs/{run_id}.yaml` 使用排他创建；已存在且内容相同视为幂等，内容不同抛 `ReportConflictError`。
2. `latest.yaml` 和 `latest.md` 写同目录临时文件、flush、fsync 后 `os.replace`。
3. YAML 使用 `yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False)`。
4. 返回 `ReportPaths(run_yaml, latest_yaml, latest_markdown)`。

`ReportWriter.load_history()` 读取 `reports/runs/*.yaml` 并用 `PipelineRunReport.model_validate` 校验，按 completed_at 排序；单个历史报告损坏抛 `ReportHistoryError`，不得静默拿错误数据计算基线。

在 `PathService` 增加 `reports_dir()`、`report_run_path()`、`report_latest_yaml_path()`、`report_latest_markdown_path()`。

- [ ] **Step 6: 实现 required ReportSink**

`ReportSink.name = "report"`、`criticality = REQUIRED`。它按 run_id 缓存去重事件；收到 RunCompleted 时先读取已存在历史报告，再调用 `build_run_report(events, baseline_reports=history)` 和 `ReportWriter.write()`，成功后保存 `latest_report/latest_paths` 供 CLI 使用。其他事件只缓存，不创建报告目录；当前 run_id 尚未写入历史，因此不会把自己当基线。

- [ ] **Step 7: 实现 JSONL 事件 reader**

`read_run_events(log_dir, run_id)` 只读取日期目录下文件名包含清理后 run_id 的 `*.jsonl`，逐行 `json.loads` 后用 `RunEvent.model_validate` 校验，再按 occurred_at/event_id 排序去重。损坏行产生 `RunLogReadError(path, line_number)`，不得静默跳过或读取旧 `.log`。

- [ ] **Step 8: 运行 reporting、run_logging 和依赖边界测试**

Run: `python -m pytest tests/reporting tests/run_logging tests/runtime/test_dependencies.py -v`

Expected: 全部通过。

- [ ] **Step 9: 提交报告持久化**

```bash
git add src/novel_material/reporting src/novel_material/run_logging/reader.py src/novel_material/infra/path_service.py tests/reporting tests/run_logging/test_run_logging_core.py
git commit -m "feat(report): 持久化机器报告与 Markdown" -m "主要改动：
- 增加确定性 Markdown 和不可变 run 报告
- 原子更新 latest YAML 与 Markdown
- 增加 required ReportSink 和轮转 JSONL 事件读取

验证结果：
- python -m pytest tests/reporting tests/run_logging tests/runtime/test_dependencies.py -v，通过"
```

### Task 8：接入完整流水线、同步门禁与终端摘要

**Files:**
- Modify: `src/novel_material/cli/pipeline_common.py`
- Modify: `src/novel_material/pipeline/orchestrator.py`
- Modify: `src/novel_material/cli/pipeline.py`
- Modify: `src/novel_material/terminal/reporter.py`
- Modify: `tests/pipeline/test_orchestrator.py`
- Modify: `tests/cli/test_pipeline_contract.py`
- Modify: `tests/terminal/test_terminal_core.py`

- [ ] **Step 1: 编写 audit 阻断 sync 的失败测试**

```python
def test_blocker_audit_stops_before_sync(monkeypatch):
    calls = []
    specs = (
        spec("analyze", RunStatus.SUCCESS),
        spec("audit", RunStatus.FAILED, blocking=True),
        StageSpec(
            "sync",
            lambda _request: calls.append("sync") or stage("sync", RunStatus.SUCCESS),
            blocking=True,
        ),
    )
    result = PipelineOrchestrator(specs).run(request())
    assert [item.name for item in result.stages] == ["analyze", "audit"]
    assert result.status is RunStatus.FAILED
    assert calls == []
```

- [ ] **Step 2: 编写报告 sink 失败降级与成功摘要失败测试**

```python
def test_report_sink_failure_degrades_successful_pipeline(monkeypatch):
    class BrokenReportSink:
        name = "report"
        criticality = SinkCriticality.REQUIRED

        def emit(self, event):
            if event.event_name == "RunCompleted":
                raise OSError("disk full")

    result = PipelineOrchestrator(
        [spec("analyze", RunStatus.SUCCESS)],
        dispatcher=RuntimeDispatcher([BrokenReportSink()]),
    ).run(request())
    assert result.status is RunStatus.DEGRADED
    assert result.diagnostics[-1].code == "event_sink_failed"


def test_terminal_completion_shows_report_path_and_top_risk(sample_report):
    terminal = RecordingTerminal()
    reporter = TerminalReporter(terminal, mode=TerminalMode.PLAIN)
    reporter.complete_report(sample_report, Path("/tmp/reports/latest.md"))
    assert "degraded" in terminal.stdout_text + terminal.stderr_text
    assert "character_profile_fallback" in terminal.stdout_text + terminal.stderr_text
    assert "/tmp/reports/latest.md" in terminal.stdout_text + terminal.stderr_text
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/terminal/test_terminal_core.py -v`

Expected: FAIL，提示 audit 尚未进入 stage plan、报告摘要方法不存在或状态不符。

- [ ] **Step 4: 构造统一 runtime sinks**

在 `pipeline_common.py` 增加私有工厂：

```python
@dataclass(frozen=True)
class PipelineRuntime:
    dispatcher: RuntimeDispatcher
    report_sink: ReportSink


def _create_pipeline_runtime(material_id: str, command: str, run_id: str) -> PipelineRuntime:
    settings = get_settings()
    log_sink = JsonlSink(
        ensure_log_dir(),
        command=command,
        run_id=run_id,
        max_bytes=int(settings["RUN_LOG_MAX_BYTES"]),
    )
    report_sink = ReportSink(NOVELS_DIR / material_id)
    return PipelineRuntime(
        dispatcher=RuntimeDispatcher([log_sink, report_sink]),
        report_sink=report_sink,
    )
```

full 在 ingest 前记录 `started_at` 与单调时钟起点；ingest 成功后为其补上外层实测 `duration_ms`，创建 runtime，并通过 `RunRequest.options["report_prior_stages"]` 只传入本次刚执行的 ingest。continue 不把历史成功阶段放入 `report_prior_stages`。Orchestrator 使用 RunRequest.started_at 发布 RunStarted，使报告总耗时覆盖 ingest，同时不会把上次运行的阶段误算到本次报告。

`run_full_pipeline()` 合并 ingest 与 remainder 时不得重新聚合丢失 remainder 的顶层可观测性诊断。增加 `combine_run_result(prior_stages, remainder, expected_stages)`：先从全部阶段生成基础结果，再把 remainder 中未包含于阶段 diagnostics 的 `event_sink_failed` 等顶层 diagnostics 合入；当基础结果为 success 而 remainder 已 degraded 时，最终结果保持 degraded/退出码 3。补充回归测试模拟 ReportSink 失败，确认 full 的最终结果不会恢复成 success。

- [ ] **Step 5: 把 audit 插到 sync 前**

`_stage_specs()` 增加 `elapsed_provider: Callable[[], float]`，顺序改为：evaluation、analyze、outline、worldbuilding、characters、tags、insights、refine、audit、sync。audit 使用 `run_artifact_audit_stage`，`blocking=True`：

```python
def _audit_stage(material_id: str, options: dict, elapsed_provider) -> StageResult:
    mode = get_runtime_mode(options.get("mode", "standard"))
    if mode.name == "fast":
        return run_artifact_audit_stage(material_id)
    settings = get_settings()
    fraction = float(settings["ARTIFACT_REVIEW_TIME_FRACTION_STANDARD"])
    max_calls_key = (
        "ARTIFACT_REVIEW_MAX_CALLS_DEEP"
        if mode.name == "deep"
        else "ARTIFACT_REVIEW_MAX_CALLS_STANDARD"
    )
    budget = ReviewBudget(
        max_seconds=max(0.0, elapsed_provider() * fraction),
        max_calls=int(settings[max_calls_key]),
        clock=time.monotonic,
    )
    return run_artifact_audit_stage(
        material_id,
        reviewer=LLMArtifactReviewer(),
        budget=budget,
    )
```

full/continue 在开始时保存单调时钟起点，并以 `lambda: time.monotonic() - run_start` 传给 `_stage_specs()`。因此 standard 的可选复审预算最多为审计开始前已耗时的 10%；单次调用实际超出估算时记录 SLO 违约，但不强杀正在返回的请求。fast 始终只运行规则审计。

`plan_continue()` 顺序同步增加 audit；旧 sidecar 没有 audit 时从 audit 继续，不重跑已经成功的 analyze/骨架阶段。

- [ ] **Step 6: 增加 `nm pipeline report` 重建命令**

命令参数为 material_id 和可选 `--run-id`。未指定时从 `PipelineStateStore.read_latest()` 取 run_id；读取 JSONL 事件，构建并写报告。命令不得调用 LLM 或修改事实 YAML。找不到事件返回失败退出码 1 和稳定 `run_events_missing` 错误。

- [ ] **Step 7: 输出终端摘要**

`TerminalReporter.complete_report(report, path)`：JSON 模式输出 report JSON；quiet 成功时不输出；TTY/plain 显示状态、总耗时、主要产物问题计数、最高严重问题 code、报告路径和第一条 next action。动态文本使用 `Text`，不解释 Rich markup。

`_finish_pipeline_command()` 优先使用 `report_sink.latest_report`；报告不存在时保留当前固定完成/失败文本。最终 Typer 退出码仍来自 RunResult，不从报告推断。

- [ ] **Step 8: 运行 pipeline、CLI、terminal、reporting 回归**

Run: `python -m pytest tests/pipeline tests/cli/test_pipeline_contract.py tests/terminal tests/reporting -v`

Expected: 全部通过。

- [ ] **Step 9: 提交流水线与终端接入**

```bash
git add src/novel_material/cli/pipeline_common.py src/novel_material/cli/pipeline.py src/novel_material/pipeline/orchestrator.py src/novel_material/terminal/reporter.py tests/pipeline tests/cli/test_pipeline_contract.py tests/terminal
git commit -m "feat(pipeline): 接入审计门禁与结束报告" -m "主要改动：
- 在同步前执行阻断式产物审计
- 为 full 和 continue 统一接入 JSONL 与报告 sinks
- 增加报告重建命令和简洁终端摘要

验证结果：
- python -m pytest tests/pipeline tests/cli/test_pipeline_contract.py tests/terminal tests/reporting -v，通过"
```

### Task 9：补齐依赖护栏、文档与第一期验收

**Files:**
- Modify: `tests/runtime/test_dependencies.py`
- Modify: `tests/cli/test_command_contracts.py`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/USER_MANUAL.md`
- Modify: `docs/REQUIREMENTS.md`
- Modify: `docs/README.md`

- [ ] **Step 1: 增加依赖和只读护栏测试**

在 `test_dependencies.py` 增加 AST 检查：

- `audit` 不得 import `storage`、`terminal`、`reporting.writer`。
- `reporting` 不得 import `storage`、业务 pipeline 实现或 `terminal`。
- `terminal` 可以 import `reporting.models`，不得 import `reporting.writer`。
- `run_logging` 继续不得 import `terminal`。

新增集成测试复制一个最小素材目录，执行 `audit_material()`、fake reviewer 和报告构建后比较所有原事实文件 SHA-256，要求完全不变；只允许新增 `reports/`。

- [ ] **Step 2: 更新权威文档**

按实际实现更新：

- `ARCHITECTURE.md`：增加 audit/reporting 模块、事件流、required ReportSink 和报告目录。
- `docs/USER_MANUAL.md`：增加 `nm validate artifacts [--review]`、`nm pipeline report`、退出码、报告示例与排障。
- `docs/REQUIREMENTS.md`：记录运行健康和产物质量报告的可验证需求，不声称检索质量提升。
- `docs/README.md`：更新文档状态和入口链接。

- [ ] **Step 3: 运行第一期完整测试**

Run: `python -m pytest tests/audit tests/reporting tests/runtime tests/run_logging tests/pipeline tests/terminal tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v`

Expected: 全部通过，0 failed。

- [ ] **Step 4: 运行静态、CLI 与工作区检查**

```bash
python -m novel_material.cli.main validate artifacts --help
python -m novel_material.cli.main pipeline report --help
python -m compileall -q src/novel_material
git diff --check -- . ':(exclude)docs/feedback.md'
git status --short
```

Expected:

- 两个帮助命令退出 0，显示 `--review` 和 `--run-id`。
- compileall 退出 0。
- 排除用户既有 `docs/feedback.md` 后，`git diff --check` 无输出。
- `git status --short` 只包含本期计划内文件和用户原有 `docs/feedback.md`，不得包含 `data/novels/`、数据库或旧日志变更。

- [ ] **Step 5: 使用真实现有素材做只读规则验收**

Run: `python -m novel_material.cli.main validate artifacts nm_novel_20260621_4si2`

Expected:

- 命令不得调用 LLM，因为未传 `--review`。
- 返回 degraded/退出码 3。
- 至少报告 `character_profile_fallback`，证据包含陈汉升缺少 `arc_summary`、`psychology` 和 `relationships`。
- 除 `reports/` 外，素材目录原有文件哈希不变。

- [ ] **Step 6: 记录性能基线但不宣称达成 10% 门禁**

使用 fake reviewer 和固定事件集运行 `pytest-benchmark` 不作为依赖；直接以 `time.perf_counter()` 在测试中记录规则审计和报告生成耗时，要求 1084 个章节索引、134 个人物档案的本地 fixture 在 2 秒内完成。真实 LLM 复审和三次同素材运行中位数留给第二期发布验收，本期报告必须把基线类型标记为 `rules_only`。

- [ ] **Step 7: 提交第一期文档与验收护栏**

```bash
git add tests/runtime/test_dependencies.py tests/cli/test_command_contracts.py ARCHITECTURE.md docs/USER_MANUAL.md docs/REQUIREMENTS.md docs/README.md
git commit -m "docs(audit): 补齐审计报告文档与验收护栏" -m "主要改动：
- 更新审计、报告、命令、状态和排障文档
- 增加依赖边界、事实文件只读和真实兜底样例验收
- 记录第一期规则模式性能基线与后续发布门禁边界

验证结果：
- 第一期开列 pytest 命令全部通过
- CLI 帮助、compileall、Git 差异和真实只读素材审计通过"
```

## 第一期完成门禁

- `nm validate artifacts <id>` 默认不调用 LLM、不修改任何事实文件。
- `nm validate artifacts <id> --review` 只在双重预算内复审可疑项，预算耗尽后明确记录未审状态。
- audit blocker 在 sync 前停止流水线并返回退出码 1；error 返回退出码 3；warning/info 不阻断。
- material_id 已经建立后，success、degraded、failed 和 interrupted 运行都尽力生成 `runs/{run_id}.yaml`、`latest.yaml` 与 `latest.md`；ingest 在创建素材目录前失败时只返回稳定终端错误，因为没有合法报告归属目录。
- 报告 sink 失败能把原成功运行降级，并留下稳定 `event_sink_failed` 诊断。
- `nm pipeline report <id> [--run-id]` 只从现有 sidecar/JSONL 重建报告，不调用 LLM。
- 终端只显示结论、耗时、最高风险、报告路径和第一条下一步命令。
- 当前真实主角兜底档案稳定触发 `character_profile_fallback` error。
- 默认测试套件无网络、无数据库、无数据迁移副作用。
- 第一阶段通过后才编写并执行第二期“前置导航与人物小传”实施计划。
