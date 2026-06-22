# 运行结果、结构化日志与终端正确性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立唯一可信的运行结果契约，把结构化日志和终端显示拆成独立消费者，并修复流水线假完成、错误退出码、日志串线和错误 ETA 等全部已确认问题。

**Architecture:** 业务层返回不可变 `RunResult` 并发布中立 `RunEvent`，`runtime` 负责 context、同步分发和汇总，`run_logging` 只负责 JSONL 持久化，`terminal` 只负责 TTY/纯文本/JSON 呈现。Pipeline 使用自己的运行状态 sidecar 支持新运行和断点判断，日志与终端都不能反推业务完成状态。

**Tech Stack:** Python 3.10+、Pydantic v2、Typer、Rich、contextvars、Python logging compatibility、PyYAML、pytest。

---

## 实施前约束

- 不修改、清洗、迁移、补写或重跑 `data/novels/` 中任何已有数据。
- 不修复当前 90 个无效 insight；它们只作为只读回归证据。
- 不迁移、改写或删除现有 `logs/*.log`；保留策略只管理新 JSONL。
- 不执行真实 LLM、embedding、PostgreSQL、storage sync、material delete 或数据库 migration。
- 所有测试使用 `tmp_path`、fake LLM、fake DB、`MemorySink` 和 `RecordingTerminal`。
- 保留用户已有的 `docs/feedback.md` 和 `eval/search_candidates.yaml` 工作区变更。
- `run_logging` 与 `terminal` 禁止相互 import；测试增加静态依赖断言。
- 不增加 OpenTelemetry SDK、Collector、消息队列、远程日志服务或新数据库。
- QueueHandler/QueueListener 只在实现后基准证明同步写日志阻塞业务时另立计划，本计划不实现。
- 每个 Task 先写失败测试、确认失败、写最小实现、运行定向与相关回归测试，再按项目中文提交规范提交。

## 文件结构与职责

### 新建文件

```text
src/novel_material/runtime/
├── __init__.py
├── contracts.py
├── context.py
├── dispatcher.py
├── diagnostics.py
├── heartbeat.py
├── summary.py
└── testing.py

src/novel_material/run_logging/
├── __init__.py
├── sink.py
├── serializer.py
├── redaction.py
├── aggregation.py
├── retention.py
└── testing.py

src/novel_material/terminal/
├── __init__.py
├── reporter.py
├── progress.py
├── eta.py
├── modes.py
├── errors.py
└── testing.py

src/novel_material/pipeline/
├── state.py
└── orchestrator.py

src/novel_material/cli/
└── pipeline_common.py
```

对应新增测试：

```text
tests/runtime/test_contracts.py
tests/runtime/test_context.py
tests/runtime/test_dispatcher.py
tests/runtime/test_summary.py
tests/runtime/test_dependencies.py
tests/run_logging/test_serializer.py
tests/run_logging/test_redaction.py
tests/run_logging/test_sink.py
tests/run_logging/test_retention.py
tests/terminal/test_reporter.py
tests/terminal/test_progress.py
tests/terminal/test_eta.py
tests/pipeline/test_state.py
tests/pipeline/test_orchestrator.py
tests/cli/test_pipeline_contract.py
tests/cli/test_command_contracts.py
tests/infra/test_llm_telemetry.py
```

### 重点修改文件

- `src/novel_material/pipeline/insights.py`：不再把缺失/invalid 结果写成成功数据，返回 `StageResult`。
- `src/novel_material/pipeline/progress.py`：历史状态变为只读检查，支持 `legacy_unverified` 和 DB `unknown`。
- `src/novel_material/pipeline/analyze.py` 及骨架阶段：发布批次事件并返回结构化结果。
- `src/novel_material/infra/llm.py`：删除全局调用详情和错误串线，发布请求级事件。
- `src/novel_material/infra/logging_config.py`：缩减为旧接口兼容层，最终不创建正式 handler。
- `src/novel_material/infra/progress.py`：迁移后删除 `silent_console`、StageTracker 和手工 spinner。
- `src/novel_material/cli/main.py`、`pipeline.py`、`search.py`、`validate.py`、`storage.py`、`material.py`、`tags.py`：统一 reporter、退出码和参数错误。
- `src/novel_material/storage/sync_core.py`：返回全量汇总，自动修复改为显式授权。
- `src/novel_material/search/service.py`：发布通道耗时、候选数与降级事件。
- `config/settings.yaml`：增加新日志保留、轮转、heartbeat 和终端 ETA 配置。
- `pyproject.toml`：增加 `novel-material` 备用 CLI 入口。
- `ARCHITECTURE.md`、`docs/USER_MANUAL.md`、`docs/REQUIREMENTS.md`、`README.md`、`docs/README.md`：同步契约与操作说明。

## 问题覆盖矩阵

| 问题 | 对应任务 |
|---|---|
| insight 失败占位、invalid 保存、无条件成功、断点跳过坏文件 | Task 4、Task 9 |
| 文件数量被当作完成、DB 异常被当作未同步、当前运行二次猜测 | Task 4、Task 9 |
| 测试污染正式日志、短进程碎片文件 | Task 1、Task 5 |
| 全局 `_call_details`、错误 request ID/attempt 串线 | Task 3、Task 6 |
| 跨日时间、文本不可解析、运行链路缺失 | Task 2、Task 5 |
| WARNING 洪水、thinking 字段矛盾 | Task 5、Task 6 |
| 原始输出/异常/密钥指纹泄漏与日志注入 | Task 5、Task 6 |
| 轮转、保留、sink 故障、heartbeat 缺失 | Task 5、Task 6 |
| 日志是否满足 pipeline、LLM、search、audit 项目需求 | Task 6、Task 10 |
| `--semantic` 命名不实 | Task 8 |
| Progress 十余处重复、full/continue 漂移 | Task 7、Task 9、Task 11 |
| `event --keyword` 无效 | Task 8 |
| StageTracker 无效字段、时间列无语义 | Task 7、Task 11 |
| 单阶段、full、continue、validate、delete、sync-all 错误退出码 | Task 8、Task 9、Task 10 |
| 不存在素材同时显示不存在和完成 | Task 4、Task 9 |
| `0:00:02` 双 ETA | Task 7 |
| `silent_console` 隐藏 WARNING/ERROR | Task 7、Task 11 |
| 非法参数暴露 traceback | Task 8 |
| 进度 100% 被当作数据成功 | Task 2、Task 7、Task 9 |
| 不确定总量 spinner 不停止 | Task 7、Task 10 |
| 分类 ETA 固定 45 秒 | Task 7、Task 10 |
| 多套终端机制、`cli/pipeline.py` 职责过载 | Task 7、Task 9、Task 11 |
| 所有错误写 stdout | Task 7、Task 8、Task 10 |
| Rich markup 解释用户数据 | Task 7、Task 8 |
| 非 TTY、窄终端、quiet/no-progress/no-color 缺失 | Task 7、Task 8 |
| 日志路径文档矛盾、终端契约缺失 | Task 11 |
| `{material_id}` 原样显示 | Task 9 |
| macOS `nm` 冲突 | Task 8、Task 11 |
| 帮助中英文混杂 | Task 11（明确保留 Typer 固定框架词，其余项目文案中文化） |
| 既有素材与旧日志不得被顺手修复 | 全部任务，Task 12 最终验证 |

## 对话需求追踪

| 用户在本次对话中的要求 | 计划落实位置 |
|---|---|
| 仔细检查 `logs/`，不能只处理表面格式 | Task 4、Task 5、Task 6、Task 9 |
| 当前数据用于测试验证，重点是完善系统 | 实施前约束、Task 1、Task 12 |
| 默认不修复、清洗或重跑已有数据，必要契约变化可以单独处理 | 数据边界、Task 4 sidecar、Task 10 显式 `--repair` |
| 修复 `24%` 时出现 `0:00:02` 的错误计时 | Task 7 假时钟批次 ETA 回归 |
| 分析整个终端交互、显示、错误和隐患 | 28 项问题覆盖矩阵、Task 7 至 Task 11 |
| 日志与终端结构化处理、低耦合、独立模块 | Task 1 依赖门禁、Task 2/3 中立契约、Task 5 与 Task 7 独立实现 |
| 判断日志是否满足项目需求并参考外部实践 | 设计说明第 10 节、Task 5/6 的 Pipeline、LLM、Search、Audit 字段 |
| 上下文压缩后重新读取完整对话并遍历全部问题 | 本表、问题覆盖矩阵、Task 12 逐项验证报告 |

---

## 阶段一：测试护栏与中立运行契约

### Task 1：隔离测试副作用并建立零数据变更护栏

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/runtime/test_dependencies.py`
- Create: `tests/runtime/test_workspace_safety.py`

- [ ] **Step 1: 编写正式日志零写入和模块依赖测试**

```python
from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[2]


def test_logging_and_terminal_do_not_import_each_other():
    forbidden = {
        "run_logging": "novel_material.terminal",
        "terminal": "novel_material.run_logging",
    }
    for package, target in forbidden.items():
        for path in (ROOT / "src" / "novel_material" / package).glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }
            assert target not in imports, f"{path} 不得依赖 {target}"


def test_test_suite_uses_isolated_log_dir(isolated_log_dir: Path):
    assert isolated_log_dir.exists()
    assert isolated_log_dir != ROOT / "logs"
    assert isolated_log_dir.is_relative_to(Path(tempfile.gettempdir()))
```

- [ ] **Step 2: 运行测试并确认依赖测试因新模块不存在而失败**

Run: `python -m pytest tests/runtime/test_dependencies.py tests/runtime/test_workspace_safety.py -v`

Expected: FAIL，提示 `src/novel_material/run_logging` 或 fixture 不存在；正式 `logs/` 不应新增文件。

- [ ] **Step 3: 在 conftest 中设置会话级临时路径**

```python
import os
from pathlib import Path
import shutil
import tempfile

import pytest


_TEST_RUNTIME_ROOT = Path(tempfile.mkdtemp(prefix="novel-material-tests-"))
os.environ["LOG_DIR"] = str(_TEST_RUNTIME_ROOT / "logs")
os.environ["NOVEL_MATERIAL_TESTING"] = "1"


@pytest.fixture(scope="session")
def isolated_log_dir() -> Path:
    path = _TEST_RUNTIME_ROOT / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_RUNTIME_ROOT, ignore_errors=True)
```

同时创建三个新 package 的空 `__init__.py`，使依赖测试能够扫描目录；业务实现留给后续 Task。

- [ ] **Step 4: 验证隔离护栏与现有测试**

Run: `python -m pytest tests/runtime/test_dependencies.py tests/runtime/test_workspace_safety.py -v && python -m pytest -q`

Expected: 新测试 PASS；全量不少于现有 `186 passed, 1 skipped`，正式 `logs/` 文件数量不增加。

- [ ] **Step 5: 提交测试护栏**

```bash
git add tests/conftest.py tests/runtime src/novel_material/runtime/__init__.py src/novel_material/run_logging/__init__.py src/novel_material/terminal/__init__.py
git commit -m "test(runtime): 建立运行改造的副作用护栏" \
  -m "主要改动：
- 将测试日志目录隔离到临时路径
- 增加日志与终端反向依赖检查
- 增加正式工作区零写入断言

验证结果：
- python -m pytest tests/runtime -v 通过
- python -m pytest -q 通过"
```

### Task 2：建立不可变运行事件与结果模型

**Files:**
- Create: `src/novel_material/runtime/contracts.py`
- Modify: `src/novel_material/runtime/__init__.py`
- Test: `tests/runtime/test_contracts.py`

- [ ] **Step 1: 编写状态、计数和退出码失败测试**

```python
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from novel_material.runtime.contracts import (
    ExitCode,
    ProgressCounts,
    RunEvent,
    RunResult,
    RunStatus,
    StageResult,
)


def test_progress_counts_reject_inconsistent_total():
    with pytest.raises(ValidationError):
        ProgressCounts(expected=10, processed=8, succeeded=7, failed=2)


def test_degraded_run_maps_to_exit_code_three():
    stage = StageResult(
        stage_id="stage-1",
        name="insights",
        status=RunStatus.DEGRADED,
        counts=ProgressCounts(
            expected=10, processed=10, succeeded=9, degraded=1
        ),
    )
    result = RunResult.from_stages(
        run_id="run-1", command="pipeline insights", stages=[stage]
    )
    assert result.status is RunStatus.DEGRADED
    assert result.exit_code is ExitCode.DEGRADED


def test_run_event_is_immutable():
    event = RunEvent(
        event_name="RunStarted",
        event_id="event-1",
        occurred_at=datetime.now(timezone.utc),
        observed_at=datetime.now(timezone.utc),
        run_id="run-1",
        command="pipeline analyze",
        component="pipeline",
        operation="analyze",
    )
    with pytest.raises(ValidationError):
        event.status = RunStatus.SUCCESS
```

- [ ] **Step 2: 运行测试并确认模型尚不存在**

Run: `python -m pytest tests/runtime/test_contracts.py -v`

Expected: FAIL，提示无法导入 `runtime.contracts`。

- [ ] **Step 3: 实现核心契约**

```python
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    DEGRADED = "degraded"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class ExitCode(IntEnum):
    SUCCESS = 0
    FAILED = 1
    USAGE = 2
    DEGRADED = 3
    INTERRUPTED = 130


class ProgressCounts(BaseModel):
    model_config = ConfigDict(frozen=True)
    expected: int = Field(default=0, ge=0)
    processed: int = Field(default=0, ge=0)
    succeeded: int = Field(default=0, ge=0)
    degraded: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    remaining: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_counts(self):
        if self.processed > self.expected:
            raise ValueError("processed 不能大于 expected")
        if self.succeeded + self.degraded + self.failed > self.processed:
            raise ValueError("结果计数不能大于 processed")
        if self.remaining != self.expected - self.processed:
            raise ValueError("remaining 必须等于 expected - processed")
        return self


class Diagnostic(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    message: str
    severity: str
    count: int = Field(default=1, ge=1)
    retryable: bool = False
    next_action: str | None = None


class StageResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    stage_id: str
    name: str
    status: RunStatus
    counts: ProgressCounts = ProgressCounts()
    duration_ms: float = Field(default=0, ge=0)
    diagnostics: tuple[Diagnostic, ...] = ()


class RunResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    command: str
    status: RunStatus
    exit_code: ExitCode
    stages: tuple[StageResult, ...] = ()
    counts: ProgressCounts = ProgressCounts()
    diagnostics: tuple[Diagnostic, ...] = ()

    @classmethod
    def from_stages(
        cls,
        run_id: str,
        command: str,
        stages: list[StageResult],
        expected_stages: int | None = None,
    ):
        status = aggregate_status(stage.status for stage in stages)
        expected = expected_stages if expected_stages is not None else len(stages)
        succeeded = sum(stage.status is RunStatus.SUCCESS for stage in stages)
        degraded = sum(stage.status is RunStatus.DEGRADED for stage in stages)
        failed = sum(stage.status is RunStatus.FAILED for stage in stages)
        return cls(
            run_id=run_id,
            command=command,
            status=status,
            exit_code=exit_code_for(status),
            stages=tuple(stages),
            counts=ProgressCounts(
                expected=expected,
                processed=len(stages),
                succeeded=succeeded,
                degraded=degraded,
                failed=failed,
                remaining=expected - len(stages),
            ),
            diagnostics=tuple(d for stage in stages for d in stage.diagnostics),
        )


class RunEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    schema_version: int = 1
    event_name: str
    event_id: str
    occurred_at: datetime
    observed_at: datetime
    severity_text: str = "INFO"
    severity_number: int = 9
    run_id: str
    stage_id: str | None = None
    request_id: str | None = None
    command: str
    component: str
    operation: str
    material_id: str | None = None
    status: RunStatus | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
```

在同一文件实现 `aggregate_status` 和 `exit_code_for`，优先级固定为 `failed > interrupted > degraded > running > pending > success`；本次运行捕获 `KeyboardInterrupt` 时直接构造 interrupted 顶层结果并退出 130。RunResult 的 counts 统计阶段，StageResult 的 counts 统计阶段内部业务项，禁止把章节数、人物数等不同单位相加。

- [ ] **Step 4: 导出契约并运行测试**

Run: `python -m pytest tests/runtime/test_contracts.py -v && python -m pytest tests/search/test_models.py -v`

Expected: 全部 PASS，既有 `SearchResponse` 契约不受影响。

- [ ] **Step 5: 提交运行契约**

```bash
git add src/novel_material/runtime tests/runtime/test_contracts.py
git commit -m "feat(runtime): 建立统一运行事件与结果契约" \
  -m "主要改动：
- 定义运行状态、退出码、计数、诊断和事件模型
- 固定阶段到总运行结果的聚合优先级
- 约束事件不可变和计数一致性

验证结果：
- python -m pytest tests/runtime/test_contracts.py -v 通过
- python -m pytest tests/search/test_models.py -v 通过"
```

### Task 3：实现请求上下文、同步分发和汇总器

**Files:**
- Create: `src/novel_material/runtime/context.py`
- Create: `src/novel_material/runtime/dispatcher.py`
- Create: `src/novel_material/runtime/diagnostics.py`
- Create: `src/novel_material/runtime/summary.py`
- Create: `src/novel_material/runtime/testing.py`
- Test: `tests/runtime/test_context.py`
- Test: `tests/runtime/test_dispatcher.py`
- Test: `tests/runtime/test_summary.py`

- [ ] **Step 1: 编写 context 隔离与 sink 故障测试**

```python
from novel_material.runtime.context import current_context, run_context, stage_context
from novel_material.runtime.dispatcher import RuntimeDispatcher
from novel_material.runtime.testing import MemoryEventSink, event


def test_nested_context_restores_parent_stage():
    assert current_context() is None
    with run_context(command="pipeline full", material_id="nm_demo") as run:
        with stage_context("analyze") as stage:
            assert current_context().stage_id == stage.stage_id
        assert current_context().stage_id is None
        assert current_context().run_id == run.run_id
    assert current_context() is None


def test_failing_sink_does_not_block_healthy_sink():
    healthy = MemoryEventSink()

    class FailingSink:
        name = "broken"
        def emit(self, _event):
            raise OSError("disk full")

    report = RuntimeDispatcher([FailingSink(), healthy]).emit(event("RunStarted"))
    assert len(healthy.events) == 1
    assert report.failed_sinks == ("broken",)
```

- [ ] **Step 2: 确认测试失败**

Run: `python -m pytest tests/runtime/test_context.py tests/runtime/test_dispatcher.py tests/runtime/test_summary.py -v`

Expected: FAIL，提示 context、dispatcher、summary 尚不存在。

- [ ] **Step 3: 实现 contextvars 和不透明 ID**

```python
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
import secrets


@dataclass(frozen=True)
class RuntimeContext:
    run_id: str
    command: str
    material_id: str | None
    stage_id: str | None = None
    request_id: str | None = None


_CURRENT: ContextVar[RuntimeContext | None] = ContextVar(
    "novel_material_runtime_context", default=None
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(16)}"


def current_context() -> RuntimeContext | None:
    return _CURRENT.get()


@contextmanager
def run_context(command: str, material_id: str | None = None):
    context = RuntimeContext(new_id("run"), command, material_id)
    token = _CURRENT.set(context)
    try:
        yield context
    finally:
        _CURRENT.reset(token)


@contextmanager
def stage_context(name: str):
    parent = require_context()
    context = replace(parent, stage_id=new_id("stage"), request_id=None)
    token = _CURRENT.set(context)
    try:
        yield context
    finally:
        _CURRENT.reset(token)
```

请求 context 同样使用 token reset；ID 只包含随机值，不包含书名、路径或查询正文。

- [ ] **Step 4: 实现 dispatcher、summary 与测试替身**

```python
from dataclasses import dataclass
from typing import Protocol

from .contracts import RunEvent


class EventSink(Protocol):
    name: str
    def emit(self, event: RunEvent) -> None: ...


@dataclass(frozen=True)
class DispatchReport:
    delivered: int
    failed_sinks: tuple[str, ...] = ()


class RuntimeDispatcher:
    def __init__(self, sinks: list[EventSink]):
        self._sinks = tuple(sinks)

    def emit(self, event: RunEvent) -> DispatchReport:
        delivered = 0
        failed = []
        for sink in self._sinks:
            try:
                sink.emit(event)
                delivered += 1
            except Exception:
                failed.append(sink.name)
        return DispatchReport(delivered, tuple(failed))
```

`summary.py` 实现 `RunSummaryAccumulator`，只按事件中的 counts、token usage 和 diagnostic code 聚合；不得读取日志或终端状态。`testing.py` 提供 `MemoryEventSink`、`FakeClock` 和构造固定时间事件的 `event()`。

`diagnostics.py` 提供无文件副作用的 `get_runtime_logger(component)` 适配器。它在调用 `.info/.warning/.error` 时读取当前 RuntimeContext 并发布 `DiagnosticRaised`；没有运行 context 的库调用使用 NullDispatcher，不创建目录、handler 或 stdout 输出。该适配器只用于逐步迁移现有 logger 调用，新增业务代码直接发布结构化事件。

- [ ] **Step 5: 运行 runtime 测试**

Run: `python -m pytest tests/runtime -v`

Expected: context 在嵌套和异常后正确恢复；sink 故障不阻塞健康 sink；Token 与诊断按 run/stage 聚合。

- [ ] **Step 6: 提交运行上下文与分发器**

```bash
git add src/novel_material/runtime tests/runtime
git commit -m "feat(runtime): 增加请求上下文与事件分发" \
  -m "主要改动：
- 使用 contextvars 隔离运行、阶段和请求上下文
- 增加同步分发和消费者故障隔离
- 增加运行计数、Token 和诊断汇总器

验证结果：
- python -m pytest tests/runtime -v 通过"
```

---

## 阶段二：流水线结果真实性

### Task 4：修复 insights 完成判定并建立 Pipeline 状态 sidecar

**Files:**
- Create: `src/novel_material/pipeline/state.py`
- Modify: `src/novel_material/pipeline/insights.py`
- Modify: `src/novel_material/pipeline/progress.py`
- Modify: `src/novel_material/validation/insights.py`
- Test: `tests/pipeline/test_state.py`
- Modify: `tests/pipeline/test_insights_pipeline.py`

- [ ] **Step 1: 编写缺失结果不落事实文件的失败测试**

```python
def test_missing_insight_is_failed_without_placeholder(
    tmp_path, monkeypatch, valid_material
):
    monkeypatch.setattr("novel_material.pipeline.insights.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.pipeline.insights.call_llm", lambda **_kwargs: {"items": []}
    )

    result = generate_chapter_insights(valid_material)

    assert result.status is RunStatus.FAILED
    assert result.counts.failed == 1
    assert result.counts.remaining == 0
    assert not (tmp_path / valid_material / "chapter_insights" / "0001.yaml").exists()


def test_invalid_existing_insight_is_pending_not_complete(tmp_path, invalid_insight_material):
    progress = inspect_pipeline_state(invalid_insight_material, novels_dir=tmp_path)
    assert progress.stages["insights"].status is RunStatus.DEGRADED
    assert progress.stages["insights"].counts.failed == 1
    assert next_pending_stage(progress) == "insights"
```

- [ ] **Step 2: 编写 DB unknown 和原子状态测试**

```python
def test_database_probe_error_is_unknown(monkeypatch, material_dir):
    monkeypatch.setattr(
        "novel_material.pipeline.progress.psycopg2.connect",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("offline")),
    )
    state = inspect_pipeline_state(material_dir.name, novels_dir=material_dir.parent)
    assert state.database.status == "unknown"
    assert state.database.diagnostic.code == "database_unreachable"


def test_state_store_replaces_file_atomically(tmp_path):
    store = PipelineStateStore(tmp_path)
    store.write(run_state("run-1", status="running"))
    store.write(run_state("run-1", status="degraded"))
    assert store.read("run-1").status == "degraded"
    assert not list((tmp_path / "runs").glob("*.tmp"))
```

- [ ] **Step 3: 运行定向测试并确认失败**

Run: `python -m pytest tests/pipeline/test_state.py tests/pipeline/test_insights_pipeline.py -v`

Expected: FAIL；当前函数返回 bool、invalid 文件仍被计为完成、DB 错误仍变成 false。

- [ ] **Step 4: 实现 sidecar 与只读 legacy 检查**

```python
class PipelineStateStore:
    def __init__(self, novel_dir: Path):
        self.runs_dir = novel_dir / "runs"

    def write(self, state: PersistedRunState) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        target = self.runs_dir / f"{state.run_id}.json"
        temp = target.with_suffix(".json.tmp")
        temp.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temp.replace(target)
        return target

    def read(self, run_id: str) -> PersistedRunState:
        return PersistedRunState.model_validate_json(
            (self.runs_dir / f"{run_id}.json").read_text(encoding="utf-8")
        )
```

`inspect_pipeline_state` 优先读取最新 sidecar；不存在时只读验证已有文件并标记 `legacy_unverified=True`。`DatabaseProbeStatus` 使用 `synced/not_synced/unknown` 三态，异常必须保留 diagnostic。

- [ ] **Step 5: 改造 insights 保存与返回逻辑**

```python
if not raw:
    diagnostics.append(
        Diagnostic(
            code="insight_missing_from_batch",
            message=f"批次 {batch_idx} 未返回第 {ch_num} 章",
            severity="error",
            retryable=True,
        )
    )
    failed += 1
    continue

errors = validate_insight(insight, profile)
if errors:
    diagnostics.append(
        Diagnostic(
            code="insight_schema_invalid",
            message=f"第 {ch_num} 章 repair 后仍有 {len(errors)} 项错误",
            severity="error",
            retryable=True,
        )
    )
    failed += 1
    continue

save_yaml(get_insight_file(novel_dir, ch_num), insight)
succeeded += 1
```

函数返回 `StageResult`。断点 pending 集合通过 `validate_insight_file()` 计算；合法文件跳过，缺失和 invalid 文件列入 pending，但本 Task 的测试不会对已有数据执行继续命令。

- [ ] **Step 6: 验证 Pipeline 状态与数据零写入测试**

Run: `python -m pytest tests/pipeline/test_state.py tests/pipeline/test_insights_pipeline.py tests/validation/test_insights.py -v`

Expected: 所有测试 PASS；fixture 中无效结果不生成 YAML；legacy 素材只读检查不写 sidecar。

- [ ] **Step 7: 提交流水线真实性修复**

```bash
git add src/novel_material/pipeline/state.py src/novel_material/pipeline/insights.py src/novel_material/pipeline/progress.py src/novel_material/validation/insights.py tests/pipeline tests/validation/test_insights.py
git commit -m "fix(pipeline): 阻止无效 insight 被标记为完成" \
  -m "主要改动：
- 缺失或 schema 无效的 insight 不再写入事实文件
- 新运行使用独立 sidecar 保存阶段结果
- 历史素材只读检查并区分数据库未知状态

影响范围：
- 不回填或修改任何已有素材
- 未来 continue 会把无效结果识别为待处理

验证结果：
- python -m pytest tests/pipeline/test_state.py tests/pipeline/test_insights_pipeline.py tests/validation/test_insights.py -v 通过"
```

---

## 阶段三：独立结构化日志

### Task 5：实现 JSONL、脱敏、聚合、轮转和保留

**Files:**
- Create: `src/novel_material/run_logging/serializer.py`
- Create: `src/novel_material/run_logging/redaction.py`
- Create: `src/novel_material/run_logging/aggregation.py`
- Create: `src/novel_material/run_logging/sink.py`
- Create: `src/novel_material/run_logging/retention.py`
- Create: `src/novel_material/run_logging/testing.py`
- Modify: `config/settings.yaml`
- Test: `tests/run_logging/test_serializer.py`
- Test: `tests/run_logging/test_redaction.py`
- Test: `tests/run_logging/test_sink.py`
- Test: `tests/run_logging/test_retention.py`

- [ ] **Step 1: 编写 JSONL schema 与脱敏失败测试**

```python
import json

from novel_material.run_logging.serializer import serialize_event
from novel_material.runtime.testing import event


def test_event_serializes_as_single_json_line():
    line = serialize_event(event("RunStarted"))
    payload = json.loads(line)
    assert "\n" not in line
    assert payload["schema_version"] == 1
    assert payload["occurred_at"].endswith("Z")
    assert payload["event_name"] == "RunStarted"


def test_sensitive_and_multiline_values_are_sanitized():
    source = event(
        "DiagnosticRaised",
        attributes={
            "authorization": "Bearer secret",
            "api_key": "sk-secret",
            "error_message": "bad\nforged=INFO",
            "prompt": "整段小说正文",
        },
    )
    payload = json.loads(serialize_event(source))
    assert payload["attributes"]["authorization"] == "[REDACTED]"
    assert payload["attributes"]["api_key"] == "[REDACTED]"
    assert "整段小说正文" not in json.dumps(payload, ensure_ascii=False)
    assert "\n" not in payload["attributes"]["error_message"]
```

- [ ] **Step 2: 编写轮转、保留与测试 sink 失败测试**

```python
def test_jsonl_sink_rotates_without_touching_legacy_logs(tmp_path):
    legacy = tmp_path / "pipeline_2026-06-21.log"
    legacy.write_text("legacy", encoding="utf-8")
    sink = JsonlSink(tmp_path, command="pipeline", run_id="run-1", max_bytes=200)
    for index in range(20):
        sink.emit(event("ProgressUpdated", attributes={"index": index}))
    assert len(list(tmp_path.rglob("pipeline_run-1*.jsonl"))) > 1
    assert legacy.read_text(encoding="utf-8") == "legacy"


def test_memory_sink_never_creates_files(tmp_path):
    sink = MemoryLogSink()
    sink.emit(event("RunStarted"))
    assert len(sink.events) == 1
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 3: 运行测试并确认模块未实现**

Run: `python -m pytest tests/run_logging -v`

Expected: FAIL，提示 serializer、sink、retention 尚不存在。

- [ ] **Step 4: 实现字段白名单和 RFC 3339 序列化**

```python
ALLOWED_TOP_LEVEL = {
    "schema_version", "event_name", "event_id", "occurred_at",
    "observed_at", "severity_text", "severity_number", "run_id",
    "stage_id", "request_id", "command", "component", "operation",
    "material_id", "status", "duration_ms", "attributes",
}
SENSITIVE_KEYS = {
    "authorization", "api_key", "password", "connection_string",
    "database_url", "prompt", "raw_content", "source_text",
}


def sanitize_value(key: str, value):
    normalized = key.lower()
    if normalized in SENSITIVE_KEYS or normalized.endswith("_secret"):
        return "[REDACTED]"
    if isinstance(value, str):
        return " ".join(value.replace("\x1b", "").splitlines())[:2000]
    if isinstance(value, dict):
        return {k: sanitize_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(key, item) for item in value[:100]]
    return value


def serialize_event(event: RunEvent) -> str:
    payload = event.model_dump(mode="json", exclude_none=True)
    payload = {k: payload[k] for k in ALLOWED_TOP_LEVEL if k in payload}
    payload["occurred_at"] = to_rfc3339(payload["occurred_at"])
    payload["observed_at"] = to_rfc3339(payload["observed_at"])
    payload["attributes"] = sanitize_value("attributes", payload.get("attributes", {}))
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
```

- [ ] **Step 5: 实现 sink、诊断聚合与新日志保留策略**

`JsonlSink.emit()` 在第一次实际事件时创建 `logs/YYYY-MM-DD/`，按 `max_bytes` 轮转为 `.1.jsonl`、`.2.jsonl`。`DiagnosticAggregator` 对相同 `(run_id, stage_id, code)` 只写前 3 条明细，结束时写一条包含总数和最多 3 个样例的汇总事件。`RetentionPolicy.apply()` 只匹配日期子目录内的 `*.jsonl`，不得匹配根目录 `*.log`。

在 `config/settings.yaml` 增加：

```yaml
RUN_LOG_MAX_BYTES: 10485760
RUN_LOG_RETENTION_DAYS: 30
RUN_LOG_MAX_FILES: 200
RUN_LOG_DIAGNOSTIC_DETAIL_LIMIT: 3
RUN_HEARTBEAT_SECONDS: 60
```

- [ ] **Step 6: 运行日志测试和正式目录零写入检查**

Run: `python -m pytest tests/run_logging tests/runtime/test_workspace_safety.py -v`

Expected: JSONL、脱敏、轮转、保留、聚合全部 PASS；旧 `.log` 保持不变；正式 `logs/` 无新增。

- [ ] **Step 7: 提交结构化日志核心**

```bash
git add src/novel_material/run_logging config/settings.yaml tests/run_logging
git commit -m "feat(logging): 增加独立结构化运行日志" \
  -m "主要改动：
- 实现 JSONL 序列化、字段白名单与敏感信息清理
- 增加重复诊断聚合、大小轮转和新日志保留策略
- 提供 MemorySink 和 NullSink 供测试使用

影响范围：
- 旧日志不迁移、不清理
- 尚未替换业务调用点

验证结果：
- python -m pytest tests/run_logging -v 通过"
```

### Task 6：接入 LLM、Pipeline、Search 和 Audit 领域事件

**Files:**
- Modify: `src/novel_material/infra/llm.py`
- Create: `src/novel_material/runtime/heartbeat.py`
- Modify: `src/novel_material/pipeline/analyze.py`
- Modify: `src/novel_material/pipeline/outline_logic.py`
- Modify: `src/novel_material/pipeline/characters_core.py`
- Modify: `src/novel_material/pipeline/worldbuilding.py`
- Modify: `src/novel_material/pipeline/tags.py`
- Modify: `src/novel_material/search/service.py`
- Modify: `src/novel_material/material/import_material.py`
- Modify: `src/novel_material/material/delete.py`
- Test: `tests/infra/test_llm_telemetry.py`
- Test: `tests/runtime/test_heartbeat.py`
- Test: `tests/run_logging/test_domain_events.py`
- Modify: `tests/search/test_service.py`

- [ ] **Step 1: 编写失败请求不得继承上一请求 ID 的测试**

```python
def test_failed_request_does_not_reuse_previous_request_id(
    runtime_recorder, fake_openai_client
):
    fake_openai_client.responses = [
        successful_response(request_id="req-success"),
        TimeoutError("timeout"),
    ]

    call_llm(**request_args(context="first"))
    with pytest.raises(TimeoutError):
        call_llm(**request_args(context="second"))

    failures = runtime_recorder.events_named("DiagnosticRaised")
    second = failures[-1]
    assert second.attributes["error_type"] == "timeout"
    assert second.request_id is None
    assert "req-success" not in second.model_dump_json()
```

- [ ] **Step 2: 编写 LLM 字段语义和 Search trace 测试**

```python
def test_disabled_thinking_does_not_emit_low_thinking_warning(runtime_recorder):
    emit_llm_completed(
        thinking_requested=False,
        reasoning_tokens=2503,
        input_tokens=100,
        output_tokens=50,
    )
    assert not runtime_recorder.diagnostics(code="thinking_tokens_below_threshold")
    event = runtime_recorder.operations(component="llm", operation="request")[-1]
    assert event.attributes["thinking_requested"] is False
    assert event.attributes["reasoning_tokens_observed"] == 2503


def test_search_emits_channel_counts_and_degradation(fake_search_service, runtime_recorder):
    fake_search_service.semantic_error = TimeoutError("slow")
    response = fake_search_service.search(search_request())
    completed = runtime_recorder.operations(component="search", operation="query")[-1]
    assert completed.attributes["mode"] == "quality"
    assert completed.attributes["candidate_counts"]["lexical"] > 0
    assert "semantic_timeout" in completed.attributes["degradation_reasons"]
    assert response.trace.degraded is True


def test_heartbeat_uses_context_without_business_payload(
    runtime_recorder, fake_clock
):
    heartbeat = HeartbeatEmitter(
        dispatcher=runtime_recorder.dispatcher,
        context=runtime_context("run-1"),
        clock=fake_clock,
        interval_seconds=60,
    )
    fake_clock.advance(60)
    heartbeat.emit_if_due()
    event = runtime_recorder.events_named("HeartbeatRecorded")[-1]
    assert event.run_id == "run-1"
    assert set(event.attributes) == {"elapsed_ms"}
```

- [ ] **Step 3: 确认当前全局统计和文本日志使测试失败**

Run: `python -m pytest tests/infra/test_llm_telemetry.py tests/runtime/test_heartbeat.py tests/run_logging/test_domain_events.py tests/search/test_service.py -v`

Expected: 新测试 FAIL；当前超时错误读取 `_call_details[-1]`，没有结构化领域事件。

- [ ] **Step 4: 将 LLM 调用改为请求局部 telemetry**

```python
@contextmanager
def llm_request_context(operation: str):
    parent = require_context()
    local = replace(parent, request_id=None)
    token = set_context(local)
    started = monotonic()
    try:
        yield LLMRequestState(operation=operation, started=started)
    finally:
        reset_context(token)


with llm_request_context(context or "llm.call") as request_state:
    try:
        response = client.chat.completions.create(**create_kwargs)
    except Exception as exc:
        emit_diagnostic(
            code=classify_error_code(exc),
            severity="error",
            retryable=is_retryable(exc),
            attributes={
                "provider": provider_name,
                "model": model_name,
                "attempt": attempt + 1,
                "max_attempts": max_attempts,
                "elapsed_ms": elapsed_ms(request_state.started),
                "error_type": classify_error_code(exc),
            },
        )
        raise
```

收到 response 后才把服务商返回 ID 写入该请求的完成事件。删除 `_call_details`、`_api_stats`、`get_last_call_*` 和 `clear_call_details`；原调用方改为使用 `RunSummaryAccumulator` 或当前 `StageResult` 的 usage。

- [ ] **Step 5: 发布项目领域事件**

固定 attributes：

```python
LLM_REQUEST_FIELDS = {
    "provider", "model", "operation", "attempt", "max_attempts",
    "timeout_seconds", "retry_delay_seconds", "finish_reason",
    "input_tokens", "output_tokens", "reasoning_tokens_observed",
    "total_tokens", "thinking_requested", "thinking_budget_requested",
    "expected_items", "returned_items", "missing_items",
    "schema_valid", "repair_attempted", "degradation_reason",
}

SEARCH_FIELDS = {
    "mode", "candidate_limit", "time_budget_seconds", "candidate_counts",
    "elapsed_ms", "embedding_version", "reranker",
    "degraded", "degradation_reasons", "query_length", "query_fingerprint",
}

AUDIT_FIELDS = {
    "action", "target_type", "target_id", "confirmed", "force",
    "repair_allowed", "before_count", "after_count", "result",
}
```

Pipeline 批次事件记录 expected/returned/missing 和校验摘要；标签字典警告通过稳定 diagnostic code 聚合。Audit 事件只在操作实际开始和结束时发布，不记录完整 YAML。

`HeartbeatEmitter` 保存显式 RuntimeContext，每 60 秒发布 `HeartbeatRecorded`；只记录 run/stage ID 和已用时间，不包含 prompt、查询或素材内容。CLI 在 RunStarted 后启动，并在 RunCompleted、异常或中断的 `finally` 中停止。测试调用 `emit_if_due()`，不真实等待。

- [ ] **Step 6: 运行领域事件与相关流水线测试**

Run: `python -m pytest tests/infra/test_llm_telemetry.py tests/runtime/test_heartbeat.py tests/run_logging/test_domain_events.py tests/search tests/pipeline -v`

Expected: 所有测试 PASS；不存在全局调用详情；日志事件不含 prompt/raw content；SearchResponse trace 与事件降级原因一致。

- [ ] **Step 7: 提交领域可观测性**

```bash
git add src/novel_material/infra/llm.py src/novel_material/runtime/heartbeat.py src/novel_material/pipeline src/novel_material/search/service.py src/novel_material/material src/novel_material/tags tests/infra tests/runtime/test_heartbeat.py tests/run_logging/test_domain_events.py tests/search
git commit -m "refactor(runtime): 统一领域事件与请求级追踪" \
  -m "主要改动：
- 移除全局 LLM 调用详情并改用请求上下文
- 补充 LLM、Pipeline、Search 和数据变更审计事件
- 统一 thinking、Token、校验和降级字段语义

验证结果：
- python -m pytest tests/infra/test_llm_telemetry.py tests/run_logging/test_domain_events.py tests/search tests/pipeline -v 通过"
```

---

## 阶段四：独立终端与 CLI 基础契约

### Task 7：实现 TerminalReporter、稳健 ETA 和 TTY 降级

**Files:**
- Create: `src/novel_material/terminal/modes.py`
- Create: `src/novel_material/terminal/eta.py`
- Create: `src/novel_material/terminal/progress.py`
- Create: `src/novel_material/terminal/reporter.py`
- Create: `src/novel_material/terminal/errors.py`
- Create: `src/novel_material/terminal/testing.py`
- Modify: `config/settings.yaml`
- Test: `tests/terminal/test_eta.py`
- Test: `tests/terminal/test_progress.py`
- Test: `tests/terminal/test_reporter.py`

- [ ] **Step 1: 用假时钟复现用户的 `0:00:02` 场景**

```python
def test_eta_uses_batch_duration_not_burst_updates():
    clock = FakeClock()
    estimator = BatchEtaEstimator(clock=clock, min_samples=2, window=5)
    estimator.start(total=1780, completed=400)

    clock.advance(180)
    estimator.complete_batch(items=10)
    clock.advance(180)
    estimator.complete_batch(items=10)

    estimate = estimator.snapshot(completed=420)
    assert estimate.elapsed_seconds == 360
    assert 6 * 60 * 60 < estimate.remaining_seconds < 8 * 60 * 60
    assert estimate.remaining_seconds != 2


def test_eta_is_estimating_before_two_batches():
    estimator = BatchEtaEstimator(clock=FakeClock(), min_samples=2, window=5)
    estimator.start(total=100, completed=0)
    assert estimator.snapshot(completed=0).remaining_seconds is None
```

- [ ] **Step 2: 编写 stdout/stderr、plain 和 markup 测试**

```python
def test_json_mode_keeps_stdout_parseable(recording_terminal):
    reporter = TerminalReporter(recording_terminal, mode=TerminalMode.JSON)
    reporter.diagnostic(error_diagnostic("database_unreachable"))
    reporter.complete(success_result())
    assert json.loads(recording_terminal.stdout) ["status"] == "success"
    assert "database_unreachable" in recording_terminal.stderr


def test_plain_mode_contains_no_ansi_or_carriage_return(recording_terminal):
    reporter = TerminalReporter(recording_terminal, mode=TerminalMode.PLAIN)
    reporter.progress(progress_event(completed=42, total=178))
    assert "\x1b[" not in recording_terminal.stderr
    assert "\r" not in recording_terminal.stderr


def test_dynamic_text_is_not_rich_markup(recording_terminal):
    reporter = TerminalReporter(recording_terminal, mode=TerminalMode.TTY)
    reporter.result_row(title="[red]危险[/red]", summary="正文")
    assert "[red]危险[/red]" in recording_terminal.rendered_text
```

- [ ] **Step 3: 运行终端测试并确认失败**

Run: `python -m pytest tests/terminal -v`

Expected: FAIL；当前没有 terminal package，Rich 默认 ETA 无法通过批次测试。

- [ ] **Step 4: 实现模式选择和双 Console 边界**

```python
class TerminalMode(str, Enum):
    TTY = "tty"
    PLAIN = "plain"
    JSON = "json"
    QUIET = "quiet"


def resolve_mode(*, json_output: bool, quiet: bool, no_progress: bool, is_tty: bool):
    if json_output:
        return TerminalMode.JSON
    if quiet:
        return TerminalMode.QUIET
    if not is_tty or no_progress:
        return TerminalMode.PLAIN
    return TerminalMode.TTY


class TerminalReporter:
    def __init__(self, streams, mode: TerminalMode, no_color: bool = False):
        self.stdout = Console(file=streams.stdout, force_terminal=False, color_system=None)
        self.stderr = Console(
            file=streams.stderr,
            force_terminal=mode is TerminalMode.TTY and not no_color,
            color_system=None if no_color else "auto",
        )
        self.mode = mode
```

所有进度和 diagnostic 进入 stderr；JSON 完成结果只写一次 stdout。动态内容包装为 `Text(value)`。

- [ ] **Step 5: 实现唯一 Progress 工厂和批次 ETA**

`create_progress()` 只使用 `SpinnerColumn`、描述、`BarColumn`、`TaskProgressColumn` 和自定义 `ElapsedRemainingColumn`，禁止 `TimeRemainingColumn`。不确定总量任务必须调用 `finish_task(task_id, status)`，把 spinner 替换为 `✓/△/✗`。

```python
class BatchEtaEstimator:
    def complete_batch(self, items: int) -> None:
        now = self.clock.monotonic()
        duration = now - self._last_batch_at
        if items > 0 and duration > 0:
            self._seconds_per_item.append(duration / items)
            self._seconds_per_item = self._seconds_per_item[-self.window:]
        self._last_batch_at = now

    def snapshot(self, completed: int) -> EtaSnapshot:
        elapsed = self.clock.monotonic() - self.started_at
        if len(self._seconds_per_item) < self.min_samples:
            return EtaSnapshot(elapsed, None)
        rate = statistics.median(self._seconds_per_item)
        return EtaSnapshot(elapsed, max(self.total - completed, 0) * rate)
```

分类任务也使用该 estimator；样本不足显示“估算中”，删除固定 45 秒。

- [ ] **Step 6: 配置终端默认值并运行测试**

在 `config/settings.yaml` 增加：

```yaml
TERMINAL_ETA_MIN_BATCHES: 2
TERMINAL_ETA_WINDOW: 5
TERMINAL_PROGRESS_REFRESH_PER_SECOND: 4
```

Run: `python -m pytest tests/terminal -v`

Expected: `420/1780` 不再产生 2 秒 ETA；plain 无 ANSI；JSON stdout 可解析；markup 保留字面值；不确定任务有明确终态。

- [ ] **Step 7: 提交独立终端模块**

```bash
git add src/novel_material/terminal config/settings.yaml tests/terminal
git commit -m "feat(terminal): 统一终端输出与批次计时" \
  -m "主要改动：
- 增加 TTY、纯文本、JSON 和 quiet 模式
- 使用真实批次耗时计算已用和剩余时间
- 统一 stdout、stderr、动态文本和任务终态

验证结果：
- python -m pytest tests/terminal -v 通过
- 用户 ETA 回归场景通过"
```

### Task 8：统一 CLI 入口、参数错误和 Search 行为

**Files:**
- Modify: `src/novel_material/cli/main.py`
- Modify: `src/novel_material/cli/search.py`
- Modify: `src/novel_material/search/serialization.py`
- Modify: `pyproject.toml`
- Create: `tests/cli/test_command_contracts.py`
- Modify: `tests/search/test_cli.py`
- Modify: `tests/test_cli_module_entrypoint.py`

- [ ] **Step 1: 编写全局模式和错误流失败测试**

```python
def test_invalid_search_limit_is_usage_error(runner):
    result = runner.invoke(app, ["search", "chapter", "雨", "--limit", "0"])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "limit" in result.stderr
    assert "Traceback" not in result.stderr


def test_search_json_stdout_is_machine_readable(runner, fake_search_service):
    result = runner.invoke(app, ["search", "chapter", "雨", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["results"] == []
    assert "spinner" not in result.stdout


def test_event_keyword_option_is_rejected(runner):
    result = runner.invoke(app, ["search", "event", "雨", "--keyword"])
    assert result.exit_code == 2
    assert "No such option" in result.stderr
```

- [ ] **Step 2: 编写 `--semantic` 弃用和备用入口测试**

```python
def test_semantic_alias_warns_and_maps_to_exact(runner, fake_search_service):
    result = runner.invoke(app, ["search", "chapter", "雨", "--semantic"])
    assert result.exit_code == 0
    assert "--semantic 已弃用" in result.stderr
    assert fake_search_service.last_request.mode == "exact"


def test_pyproject_exposes_non_conflicting_entrypoint():
    scripts = tomllib.loads(Path("pyproject.toml").read_text())["project"]["scripts"]
    assert scripts["nm"] == "novel_material.cli:main"
    assert scripts["novel-material"] == "novel_material.cli:main"
```

- [ ] **Step 3: 运行 CLI/Search 测试并确认失败**

Run: `python -m pytest tests/cli/test_command_contracts.py tests/search/test_cli.py tests/test_cli_module_entrypoint.py -v`

Expected: 参数错误仍可能带 traceback；stderr 契约、全局模式和备用入口尚未实现。

- [ ] **Step 4: 增加全局选项和 reporter context**

```python
@app.callback()
def configure_cli(
    ctx: typer.Context,
    quiet: bool = typer.Option(False, "--quiet"),
    no_progress: bool = typer.Option(False, "--no-progress"),
    no_color: bool = typer.Option(False, "--no-color"),
):
    ctx.ensure_object(dict)
    ctx.obj["terminal_options"] = TerminalOptions(
        quiet=quiet,
        no_progress=no_progress,
        no_color=no_color,
    )
```

命令通过 `get_reporter(ctx, json_output=...)` 获取 reporter；禁止模块级 `Console()`。Pydantic `ValidationError` 转为 `typer.BadParameter`，Typer 参数增加 `min/max` 或 Enum。

- [ ] **Step 5: 清理 Search 选项和数据渲染**

删除 `event` 的 `keyword_mode` 参数。`--semantic` 保留一个版本作为 hidden alias，使用时向 stderr 发弃用提示并映射为 `exact`；显式同时传 `--mode quality --semantic` 时退出 2，避免静默覆盖。

```python
def _search_mode(mode: SearchMode, semantic: bool, reporter: TerminalReporter):
    if semantic and mode != SearchMode.QUALITY:
        raise typer.BadParameter("--semantic 不能与显式 --mode 同时使用")
    if semantic:
        reporter.warning("--semantic 已弃用，请改用 --mode exact")
        return SearchMode.EXACT
    return mode
```

所有表格单元使用 `Text(result.title)`、`Text(summary)`、`Text(material_id)`。

- [ ] **Step 6: 增加备用入口并运行测试**

`pyproject.toml`：

```toml
[project.scripts]
nm = "novel_material.cli:main"
novel-material = "novel_material.cli:main"
```

Run: `python -m pytest tests/cli/test_command_contracts.py tests/search/test_cli.py tests/test_cli_module_entrypoint.py -v`

Expected: 全部 PASS；错误只在 stderr；JSON stdout 可解析；无效选项和参数退出 2。

- [ ] **Step 7: 提交 CLI 基础契约**

```bash
git add src/novel_material/cli/main.py src/novel_material/cli/search.py src/novel_material/search/serialization.py pyproject.toml tests/cli tests/search/test_cli.py tests/test_cli_module_entrypoint.py
git commit -m "fix(cli): 统一参数错误与机器输出契约" \
  -m "主要改动：
- 增加 quiet、no-progress 和 no-color 全局选项
- 修复 Search 无效选项、模式命名和 Rich markup
- 增加不冲突的 novel-material 命令入口

验证结果：
- python -m pytest tests/cli/test_command_contracts.py tests/search/test_cli.py tests/test_cli_module_entrypoint.py -v 通过"
```

---

## 阶段五：命令编排与失败语义

### Task 9：统一 Pipeline 单阶段、full、continue 和 status

**Files:**
- Create: `src/novel_material/pipeline/orchestrator.py`
- Create: `src/novel_material/cli/pipeline_common.py`
- Modify: `src/novel_material/cli/pipeline.py`
- Modify: `src/novel_material/pipeline/ingest.py`
- Modify: `src/novel_material/pipeline/analyze.py`
- Modify: `src/novel_material/pipeline/outline.py`
- Modify: `src/novel_material/pipeline/worldbuilding.py`
- Modify: `src/novel_material/pipeline/characters.py`
- Modify: `src/novel_material/pipeline/tags.py`
- Modify: `src/novel_material/pipeline/refine.py`
- Test: `tests/pipeline/test_orchestrator.py`
- Create: `tests/cli/test_pipeline_contract.py`

- [ ] **Step 1: 编写阶段失败聚合和 continue 顺序测试**

```python
def test_orchestrator_keeps_processing_allowed_failures():
    stages = [
        fake_stage("analyze", RunStatus.DEGRADED),
        fake_stage("outline", RunStatus.SUCCESS),
        fake_stage("sync", RunStatus.FAILED, blocking=True),
    ]
    result = PipelineOrchestrator(stages).run(run_request())
    assert [stage.name for stage in result.stages] == ["analyze", "outline", "sync"]
    assert result.status is RunStatus.FAILED
    assert result.exit_code == 1


def test_continue_uses_pipeline_state_not_file_count(legacy_invalid_state):
    plan = PipelineOrchestrator(default_stages()).plan_continue(legacy_invalid_state)
    assert plan.first_stage == "insights"
    assert "sync" in plan.stage_names


def test_observability_sink_failure_degrades_successful_run(failing_log_sink):
    orchestrator = PipelineOrchestrator(
        [fake_stage("analyze", RunStatus.SUCCESS)],
        dispatcher=dispatcher_with(failing_log_sink, MemoryEventSink()),
    )
    result = orchestrator.run(run_request())
    assert result.status is RunStatus.DEGRADED
    assert result.exit_code == 3
    assert result.diagnostics[0].code == "event_sink_failed"
```

- [ ] **Step 2: 编写 CLI 退出码和不存在素材测试**

```python
@pytest.mark.parametrize("command", ["ingest", "outline", "worldbuilding", "characters", "tags"])
def test_single_stage_failure_exits_one(runner, command, failing_stage):
    result = runner.invoke(app, ["pipeline", command, failing_stage.argument])
    assert result.exit_code == 1
    assert "完成" not in result.stdout
    assert "失败" in result.stderr


def test_missing_material_status_is_not_complete(runner):
    result = runner.invoke(app, ["pipeline", "status", "nm_missing"])
    assert result.exit_code == 1
    assert "素材目录不存在" in result.stderr
    assert "流水线已完成" not in result.stdout + result.stderr
```

- [ ] **Step 3: 确认当前 full/continue 和单阶段测试失败**

Run: `python -m pytest tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py -v`

Expected: 当前命令忽略返回值、重复 Progress，并通过二次扫描猜测结果，测试 FAIL。

- [ ] **Step 4: 实现 PipelineOrchestrator**

```python
@dataclass(frozen=True)
class StageSpec:
    name: str
    execute: Callable[[RunRequest], StageResult]
    blocking: bool
    enabled: Callable[[RunRequest], bool] = lambda _request: True


class PipelineOrchestrator:
    def run(self, request: RunRequest) -> RunResult:
        results = []
        for spec in self._stages:
            if not spec.enabled(request):
                continue
            with stage_context(spec.name):
                result = spec.execute(request)
            results.append(result)
            self._state_store.record(result)
            if spec.blocking and result.status is RunStatus.FAILED:
                break
        return RunResult.from_stages(
            request.run_id,
            request.command,
            results,
            expected_stages=len(self._enabled_stages(request)),
        )
```

`full` 和 `continue` 只负责构造 `RunRequest` 和 stage plan，不再复制阶段调用。当前运行摘要直接使用返回结果；`get_pipeline_progress()` 仅供 status/continue 的历史读取。

Orchestrator 在开始、每阶段前后和结束分别发布 `RunStarted`、`StageStarted`、`StageCompleted`、`RunCompleted`。每次检查 `DispatchReport.failed_sinks`；业务结果原本成功但存在 sink failure 时，通过 `with_observability_degradation()` 增加 `event_sink_failed` diagnostic 并改为 degraded/exit 3。备用 stderr 由 CLI 直接写一次固定消息，不能再次经过 dispatcher，避免递归失败。

- [ ] **Step 5: 统一阶段 adapter 和 next action**

每个阶段返回 `StageResult`。过渡期间旧 bool/string 返回值通过 `adapt_stage_result(name, value)` 转换，并在一个 Task 内移除该阶段的适配。禁止 bool 失败被当作 success。

```python
def render_next_actions(result: RunResult, material_id: str) -> tuple[str, ...]:
    actions = []
    if result.status in {RunStatus.DEGRADED, RunStatus.FAILED}:
        actions.append(f"python -m novel_material.cli.main pipeline status {material_id}")
        actions.append(f"python -m novel_material.cli.main pipeline continue {material_id}")
    return tuple(actions)
```

此处同时修复两处 `{material_id}` 原样输出。

- [ ] **Step 6: 接入 TerminalReporter 与退出码**

`pipeline.py` 的每个命令统一：

```python
result = orchestrator.run(request)
reporter.complete(result)
raise typer.Exit(int(result.exit_code))
```

`KeyboardInterrupt` 转为 interrupted `RunResult` 并退出 130。进度事件由 TerminalReporter 消费，不再使用 `silent_console`。

- [ ] **Step 7: 运行 Pipeline 契约与全量测试**

Run: `python -m pytest tests/pipeline tests/cli/test_pipeline_contract.py tests/terminal -v && python -m pytest -q`

Expected: 单阶段/full/continue/status 退出语义一致；100% 处理进度与成功计数分开；全量测试通过。

- [ ] **Step 8: 提交 Pipeline 编排改造**

```bash
git add src/novel_material/pipeline src/novel_material/cli/pipeline.py src/novel_material/cli/pipeline_common.py tests/pipeline tests/cli/test_pipeline_contract.py
git commit -m "refactor(pipeline): 统一阶段编排与完成语义" \
  -m "主要改动：
- full、continue 和单阶段命令统一返回 RunResult
- 阻断失败、允许降级和用户中断使用一致状态
- 当前运行不再通过文件或数据库二次猜测成功

影响范围：
- 不执行或改写任何已有素材
- 历史状态查询保持只读

验证结果：
- python -m pytest tests/pipeline tests/cli/test_pipeline_contract.py tests/terminal -v 通过
- python -m pytest -q 通过"
```

### Task 10：修复 Validate、Storage、Material、Tags 的结果与审计语义

**Files:**
- Modify: `src/novel_material/cli/validate.py`
- Modify: `src/novel_material/cli/storage.py`
- Modify: `src/novel_material/cli/material.py`
- Modify: `src/novel_material/cli/tags.py`
- Modify: `src/novel_material/storage/sync_core.py`
- Modify: `src/novel_material/storage/sync.py`
- Create: `src/novel_material/tags/service.py`
- Test: `tests/cli/test_command_contracts.py`
- Create: `tests/storage/test_sync_summary.py`
- Modify: `tests/test_classify.py`

- [ ] **Step 1: 编写 Validate、Delete 和 SyncSummary 失败测试**

```python
def test_validate_all_exits_one_when_any_material_fails(runner, fake_validator):
    fake_validator.results = {"nm_ok": True, "nm_bad": False}
    result = runner.invoke(app, ["validate", "validate", "--all"])
    assert result.exit_code == 1
    assert "nm_bad" in result.stderr + result.stdout


def test_delete_failure_exits_one(runner, monkeypatch):
    monkeypatch.setattr("novel_material.cli.material.delete_material", lambda *_a, **_k: False)
    result = runner.invoke(app, ["material", "delete", "--id", "nm_demo", "--force"])
    assert result.exit_code == 1
    assert "删除失败" in result.stderr


def test_sync_all_distinguishes_empty_partial_and_failed(monkeypatch, tmp_path):
    summary = sync_all(novels_dir=tmp_path, repair_allowed=False)
    assert summary.total == 0
    assert summary.succeeded == 0
    assert summary.failed == 0
    assert summary.status is RunStatus.SUCCESS
```

- [ ] **Step 2: 编写默认同步不得自动修复的测试**

```python
def test_sync_does_not_repair_without_explicit_flag(monkeypatch, material_dir):
    repair = Mock()
    monkeypatch.setattr("novel_material.storage.sync_core.repair_short_summaries", repair)
    result = sync_novel(material_dir.name, repair_allowed=False)
    assert result.status is RunStatus.FAILED
    assert result.diagnostics[0].code == "sync_precheck_failed"
    repair.assert_not_called()


def test_sync_repair_requires_confirmation_in_cli(runner):
    result = runner.invoke(app, ["storage", "sync", "nm_demo", "--repair"], input="n\n")
    assert result.exit_code == 0
    assert "未执行同步" in result.stdout
```

- [ ] **Step 3: 运行命令测试并确认当前行为失败**

Run: `python -m pytest tests/cli/test_command_contracts.py tests/storage/test_sync_summary.py tests/test_classify.py -v`

Expected: Validate/删除退出码、sync_all int 返回值、自动修复默认行为和固定分类 ETA 使测试 FAIL。

- [ ] **Step 4: 实现 SyncSummary 和显式修复授权**

```python
class SyncSummary(BaseModel):
    total: int
    succeeded: int
    failed: int
    skipped: int
    results: tuple[StageResult, ...] = ()

    @property
    def status(self) -> RunStatus:
        if self.failed == 0:
            return RunStatus.SUCCESS
        if self.succeeded > 0:
            return RunStatus.DEGRADED
        return RunStatus.FAILED


def sync_novel(
    material_id: str,
    provider: str | None = None,
    use_window: bool = False,
    *,
    repair_allowed: bool = False,
) -> StageResult:
    try:
        _precheck_schema(material_id, verbose=True)
    except QualityCheckError as exc:
        if not repair_allowed:
            return failed_sync_precheck(material_id, exc)
        return repair_then_sync(material_id, exc, provider, use_window)
```

CLI 增加 `--repair`。使用时在非 `--force` 情况下明确提示“会修改 YAML、调用 LLM 并产生费用”，确认后才设置 `repair_allowed=True`。

- [ ] **Step 5: 统一命令退出码、终态和 audit**

- Validate 单素材失败或 `--all` 任一失败：exit 1。
- Material 缺少 `--id`：exit 2；用户取消：exit 0；执行失败：exit 1。
- Storage 全量：success 0、degraded 3、failed 1；空集合显示“没有可同步素材”并 exit 0。
- Tags add/remove/move/set-synonym 和 storage migration 发布 `AuditRecorded` 开始/结束事件。
- import/delete/sync 使用同一 audit 字段，不包含完整数据。
- 所有不确定总量任务通过 TerminalReporter 结束，不残留 spinner。
- 分类使用 `BatchEtaEstimator`；不足两个真实样本显示“估算中”。

- [ ] **Step 6: 运行命令、storage 与 audit 测试**

Run: `python -m pytest tests/cli/test_command_contracts.py tests/storage tests/test_classify.py tests/run_logging/test_domain_events.py -v`

Expected: 所有命令结果、显式 repair、副作用提示、audit 和分类 ETA 测试 PASS。

- [ ] **Step 7: 提交剩余命令契约**

```bash
git add src/novel_material/cli/validate.py src/novel_material/cli/storage.py src/novel_material/cli/material.py src/novel_material/cli/tags.py src/novel_material/storage tests/cli tests/storage tests/test_classify.py tests/run_logging/test_domain_events.py
git commit -m "fix(cli): 补齐校验同步与素材操作结果语义" \
  -m "主要改动：
- 修复 validate、delete 和全量 sync 的退出码与汇总
- 将同步自动修复改为显式授权并提示数据副作用
- 为数据变更命令增加结构化审计事件

验证结果：
- python -m pytest tests/cli/test_command_contracts.py tests/storage tests/test_classify.py tests/run_logging/test_domain_events.py -v 通过"
```

---

## 阶段六：移除旧耦合、文档和最终验收

### Task 11：删除旧终端/日志机制并同步文档

**Files:**
- Delete after migration: `src/novel_material/infra/progress.py`
- Modify: `src/novel_material/infra/logging_config.py`
- Modify: `src/novel_material/infra/logging_service.py`
- Modify: `src/novel_material/infra/__init__.py`
- Modify: `src/novel_material/cli/pipeline.py`
- Modify: `src/novel_material/pipeline/analyze.py`
- Modify: `src/novel_material/pipeline/analyze_batch.py`
- Modify: `src/novel_material/pipeline/analyze_files.py`
- Modify: `src/novel_material/pipeline/analyze_utils.py`
- Modify: `src/novel_material/pipeline/characters_core.py`
- Modify: `src/novel_material/pipeline/characters_layer.py`
- Modify: `src/novel_material/pipeline/embed_all.py`
- Modify: `src/novel_material/pipeline/evaluate.py`
- Modify: `src/novel_material/pipeline/infer.py`
- Modify: `src/novel_material/pipeline/ingest.py`
- Modify: `src/novel_material/pipeline/insights.py`
- Modify: `src/novel_material/pipeline/loader.py`
- Modify: `src/novel_material/pipeline/outline_acts.py`
- Modify: `src/novel_material/pipeline/outline_beats.py`
- Modify: `src/novel_material/pipeline/outline_io.py`
- Modify: `src/novel_material/pipeline/outline_logic.py`
- Modify: `src/novel_material/pipeline/refine.py`
- Modify: `src/novel_material/pipeline/tags.py`
- Modify: `src/novel_material/pipeline/worldbuilding.py`
- Modify: `src/novel_material/storage/repair.py`
- Modify: `src/novel_material/storage/sync_core.py`
- Modify: `src/novel_material/storage/sync_utils.py`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/REQUIREMENTS.md`
- Modify: `docs/USER_MANUAL.md`
- Modify: `docs/README.md`
- Modify: `README.md`
- Modify: `tests/scripts/test_check_v3_docs.py`
- Modify: `tests/runtime/test_dependencies.py`

- [ ] **Step 1: 编写禁止旧机制的静态测试**

```python
def test_business_and_cli_do_not_use_terminal_primitives():
    forbidden = (
        "silent_console", "TimeRemainingColumn", "sys.stdout.write(",
        "logging.StreamHandler(sys.stdout)",
    )
    roots = [ROOT / "src" / "novel_material" / "pipeline", ROOT / "src" / "novel_material" / "cli"]
    violations = []
    for root in roots:
        for path in root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            violations.extend(f"{path}:{token}" for token in forbidden if token in text)
    assert violations == []


def test_pipeline_cli_is_only_command_adapter():
    source = (ROOT / "src/novel_material/cli/pipeline.py").read_text(encoding="utf-8")
    assert "PipelineOrchestrator" in source
    assert source.count("Progress(") == 0
```

- [ ] **Step 2: 运行静态测试并确认旧机制仍存在**

Run: `python -m pytest tests/runtime/test_dependencies.py -v`

Expected: FAIL，并列出 `silent_console`、`TimeRemainingColumn`、直接 stdout handler 或重复 Progress。

- [ ] **Step 3: 删除旧耦合并收紧兼容层**

- 所有调用点迁移完成后删除 `infra/progress.py`。
- 上述所有 Pipeline/Storage 文件把 `get_pipeline_logger` 替换为 `get_runtime_logger(component)`；`PipelineRunner`、`StageTracker` 和 `save_run_history` 分别替换为 stage context、RunSummaryAccumulator 和 PipelineStateStore。
- `infra/__init__.py` 停止导出 StageTracker、PipelineRunner 和 stage_context。
- `logging_config.py` 不再创建 file/stream handler，只提供旧 `get_*_logger()` 到 Runtime diagnostic 的短期适配，并发出一次 DeprecationWarning。
- `logging_service.py` 改为构造 `JsonlSink` 或删除；不得在 import 时创建目录或文件。
- `cli/pipeline.py` 只保留 Typer 参数和 orchestrator 调用，目标不超过 350 行。
- 项目代码中不得保留 `TimeRemainingColumn`、手工 spinner 和 logger handler 暂停/恢复。

- [ ] **Step 4: 更新架构和用户契约**

文档必须准确写明：

```text
日志路径：logs/YYYY-MM-DD/{command}_{run_id}.jsonl
旧日志：只读保留，不迁移、不自动删除
退出码：0 成功、1 失败、2 参数错误、3 降级完成、130 中断
stdout：正常结果和 JSON
stderr：进度、警告、错误和诊断
storage sync：默认只校验与同步，--repair 才允许修改 YAML 和调用 LLM
macOS：先执行 command -v nm；冲突时使用 novel-material 或 python -m novel_material.cli.main
```

帮助界面中项目自定义说明全部使用中文；Typer/Click 固定的 `Usage/Options/Commands` 框架标签本版本保留，不为本地化 fork CLI 框架，并在文档中明确这项非阻断取舍。

- [ ] **Step 5: 更新文档一致性测试并验证**

Run: `python -m pytest tests/runtime/test_dependencies.py tests/scripts/test_check_v3_docs.py -v && rg -n "TimeRemainingColumn|silent_console|logging.StreamHandler\(sys.stdout\)|data/novels/\{material_id\}/pipeline_" src ARCHITECTURE.md docs README.md`

Expected: pytest PASS；`rg` 无匹配；日志路径、命令入口和退出码在现行文档中一致。

- [ ] **Step 6: 提交旧机制清理与文档**

```bash
git add src/novel_material/infra src/novel_material/runtime/diagnostics.py src/novel_material/pipeline src/novel_material/storage src/novel_material/cli/pipeline.py ARCHITECTURE.md docs/REQUIREMENTS.md docs/USER_MANUAL.md docs/README.md README.md tests/runtime/test_dependencies.py tests/scripts/test_check_v3_docs.py
git commit -m "refactor(runtime): 移除旧日志终端耦合" \
  -m "主要改动：
- 删除 silent_console、重复 Progress 和 stdout 日志 handler
- 将 Pipeline CLI 收敛为命令适配层
- 统一日志路径、终端契约和 macOS 命令说明

验证结果：
- python -m pytest tests/runtime/test_dependencies.py tests/scripts/test_check_v3_docs.py -v 通过
- 静态搜索未发现旧终端机制"
```

### Task 12：执行全量回归与零数据变更验收

**Files:**
- Modify if coverage gaps remain: `docs/code-review-report.md`
- Create: `docs/runtime-observability-verification.md`

- [ ] **Step 1: 记录已有素材和旧日志基线摘要**

Run:

```bash
find data/novels -type f -exec shasum -a 256 {} \; | sort > /tmp/novel-material-data-before.sha256
find logs -maxdepth 1 -type f -name '*.log' -exec shasum -a 256 {} \; | sort > /tmp/novel-material-legacy-logs-before.sha256
```

Expected: 两份摘要文件成功生成；不访问数据库或外部 API。

- [ ] **Step 2: 运行格式、编译和全量测试**

Run:

```bash
python -m compileall -q src tests
python -m pytest -q
```

Expected: 编译成功；全量测试全部通过，允许保留项目已有明确 skip；正式 `logs/` 不新增测试日志。

- [ ] **Step 3: 运行关键契约回归组**

Run:

```bash
python -m pytest \
  tests/runtime \
  tests/run_logging \
  tests/terminal \
  tests/cli/test_pipeline_contract.py \
  tests/cli/test_command_contracts.py \
  tests/infra/test_llm_telemetry.py \
  tests/pipeline/test_state.py \
  tests/pipeline/test_orchestrator.py \
  tests/storage/test_sync_summary.py -v
```

Expected: 全部 PASS；覆盖 sink 故障、错误 request ID、invalid insight、DB unknown、退出码、stdout/stderr、JSON、TTY/plain、ETA 和 audit。

- [ ] **Step 4: 验证已有数据和旧日志摘要完全不变**

Run:

```bash
find data/novels -type f -exec shasum -a 256 {} \; | sort > /tmp/novel-material-data-after.sha256
find logs -maxdepth 1 -type f -name '*.log' -exec shasum -a 256 {} \; | sort > /tmp/novel-material-legacy-logs-after.sha256
diff -u /tmp/novel-material-data-before.sha256 /tmp/novel-material-data-after.sha256
diff -u /tmp/novel-material-legacy-logs-before.sha256 /tmp/novel-material-legacy-logs-after.sha256
```

Expected: 两次 `diff` 均无输出且退出 0。

- [ ] **Step 5: 逐项关闭审计报告问题**

在 `docs/runtime-observability-verification.md` 建立 28 行验证表，每行包含：报告问题标题、对应 Task、测试名称、验证命令和结果。额外记录日志系统的 10 项缺口、insight 假完成链路、数据零变更摘要和外部规范采用边界。

不得把未验证项写成“已修复”；如某项因环境限制无法执行，必须写“未验证”和具体原因。

- [ ] **Step 6: 最终检查计划约束与 Git 变更**

Run: `git status --short && git diff --check && git diff -- data/novels logs`

Expected: 无空白错误；`data/novels` 和旧 `logs` 无 diff；用户原有 `docs/feedback.md`、`eval/search_candidates.yaml` 变更仍保留且未纳入本任务提交。

- [ ] **Step 7: 提交验证报告**

```bash
git add docs/code-review-report.md docs/runtime-observability-verification.md
git commit -m "docs(runtime): 记录运行可靠性改造验收结果" \
  -m "主要改动：
- 将终端审计与日志缺口逐项映射到自动化验证
- 记录全量测试和关键契约回归结果
- 记录已有素材与旧日志零变化证明

验证结果：
- python -m pytest -q 通过
- 数据与旧日志摘要 diff 无变化"
```

---

## 实施完成判定

只有同时满足以下条件，才能宣称本计划完成：

1. 业务结果、日志 RunCompleted、终端摘要和退出码使用同一个 `RunResult`。
2. 无效 insight 不被计入成功，数据库不可达不被显示为未同步。
3. 用户报告的 `420/1780` 场景不再出现秒级假 ETA。
4. `run_logging` 和 `terminal` 通过静态依赖测试，互不 import。
5. Pipeline、Validate、Storage、Material 的所有失败路径返回正确非零退出码。
6. JSON 模式 stdout 始终可解析，diagnostic 与进度只在 stderr。
7. 新日志通过 schema、脱敏、轮转、保留、heartbeat、领域字段和 audit 测试。
8. 正式测试不生成日志文件。
9. 审计报告 28 项问题均有测试证据或明确非阻断取舍。
10. 已有素材、旧日志和用户工作区变更保持不变。
