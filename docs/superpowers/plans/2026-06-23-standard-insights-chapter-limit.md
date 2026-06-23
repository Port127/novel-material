# Standard 模式 Insights 章节上限 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `full` 与 `continue` 的 `standard` 模式只自动生成开头 100 章 insights，同时保持全书 L1/refine、`deep` 全量和独立 insights 命令的现有控制能力。

**Architecture:** 在 `RuntimeMode` 中增加自动 core insights 的章节上限，并从 `config/settings.yaml` 读取 `standard` 默认值；统一流水线编排器根据模式把 `start_ch/end_ch` 传给现有 `run_insights_stage`。不修改 insight 生成器的筛选、断点续传和文件格式，只收紧自动编排入口。

**Tech Stack:** Python 3.11+、Typer、pytest、YAML 配置、现有 `PipelineOrchestrator`/`StageSpec` 契约。

---

## 文件结构

- 修改 `config/settings.yaml`：声明 `INSIGHTS_STANDARD_CHAPTER_LIMIT` 的唯一可调整配置值。
- 修改 `src/novel_material/pipeline/runtime_modes.py`：校验配置并向运行模式暴露自动 insights 章节上限。
- 修改 `src/novel_material/cli/pipeline_common.py`：把运行模式范围传入统一 insights 阶段，供 `full` 和 `continue` 共用。
- 修改 `tests/pipeline/test_runtime_modes.py`：覆盖三种模式和非法配置。
- 新建 `tests/cli/test_pipeline_common.py`：覆盖统一编排器传递的 insights 范围。
- 修改 `tests/cli/test_command_contracts.py`：锁定独立 insights 命令显式范围不受自动上限影响。
- 修改 `docs/USER_MANUAL.md`、`ARCHITECTURE.md`：说明自动模式、手动命令和 refine 的边界。

### Task 1：为运行模式增加配置驱动的章节上限

**Files:**
- Modify: `config/settings.yaml`
- Modify: `src/novel_material/pipeline/runtime_modes.py`
- Test: `tests/pipeline/test_runtime_modes.py`

- [ ] **Step 1：先写运行模式失败测试**

把 `tests/pipeline/test_runtime_modes.py` 更新为：

```python
"""运行模式配置测试。"""

import pytest

from novel_material.pipeline import runtime_modes


def test_standard_mode_defaults_to_first_100_insight_chapters(monkeypatch):
    monkeypatch.setattr(
        runtime_modes,
        "get_settings",
        lambda: {"INSIGHTS_STANDARD_CHAPTER_LIMIT": 100},
    )

    mode = runtime_modes.get_runtime_mode("standard")

    assert mode.name == "standard"
    assert mode.include_core_insights is True
    assert mode.block_on_deep_insights is False
    assert mode.insight_batch_size >= 10
    assert mode.insight_depth == "core"
    assert mode.core_insight_chapter_limit == 100


def test_fast_mode_skips_blocking_insights():
    mode = runtime_modes.get_runtime_mode("fast")
    assert mode.include_core_insights is False
    assert mode.block_on_deep_insights is False
    assert mode.core_insight_chapter_limit == 0


def test_deep_mode_keeps_full_core_insights():
    mode = runtime_modes.get_runtime_mode("deep")
    assert mode.include_core_insights is True
    assert mode.include_deep_insights is True
    assert mode.key_chapter_rate > 0
    assert mode.core_insight_chapter_limit is None


@pytest.mark.parametrize("value", [0, -1, "100", True])
def test_standard_mode_rejects_invalid_chapter_limit(monkeypatch, value):
    monkeypatch.setattr(
        runtime_modes,
        "get_settings",
        lambda: {"INSIGHTS_STANDARD_CHAPTER_LIMIT": value},
    )

    with pytest.raises(ValueError, match="INSIGHTS_STANDARD_CHAPTER_LIMIT"):
        runtime_modes.get_runtime_mode("standard")


def test_standard_mode_uses_safe_fallback_when_setting_is_missing(monkeypatch):
    monkeypatch.setattr(runtime_modes, "get_settings", lambda: {})

    assert runtime_modes.get_runtime_mode("standard").core_insight_chapter_limit == 100
```

- [ ] **Step 2：运行测试并确认 RED**

Run:

```bash
pytest -q tests/pipeline/test_runtime_modes.py
```

Expected: FAIL，错误指向 `RuntimeMode` 没有 `core_insight_chapter_limit`，证明测试覆盖的是尚未实现的新契约。

- [ ] **Step 3：添加配置并实现最小运行模式逻辑**

在 `config/settings.yaml` 的 insights 配置区加入：

```yaml
# standard 自动流水线只对开头 N 章生成 L2 insights
INSIGHTS_STANDARD_CHAPTER_LIMIT: 100
```

在 `src/novel_material/pipeline/runtime_modes.py` 的现有字段之后增加上限字段，并补充配置依赖与默认常量：

```python
from dataclasses import dataclass, replace

from novel_material.infra.config import get_settings

STANDARD_INSIGHT_CHAPTER_LIMIT_DEFAULT = 100


@dataclass(frozen=True)
class RuntimeMode:
    name: str
    include_core_insights: bool
    include_deep_insights: bool
    block_on_deep_insights: bool
    insight_depth: str
    insight_batch_size: int
    key_chapter_rate: float
    core_insight_chapter_limit: int | None
```

三个 `_MODES` 条目分别增加：

```python
core_insight_chapter_limit=0       # fast
core_insight_chapter_limit=STANDARD_INSIGHT_CHAPTER_LIMIT_DEFAULT  # standard，返回时由配置覆盖
core_insight_chapter_limit=None    # deep
```

在 `get_runtime_mode` 返回前加入配置解析：

```python
    mode = _MODES[mode_name]
    if mode_name != "standard":
        return mode

    value = get_settings().get(
        "INSIGHTS_STANDARD_CHAPTER_LIMIT",
        STANDARD_INSIGHT_CHAPTER_LIMIT_DEFAULT,
    )
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(
            "INSIGHTS_STANDARD_CHAPTER_LIMIT 必须是正整数，"
            f"实际为: {value!r}"
        )
    return replace(mode, core_insight_chapter_limit=value)
```

- [ ] **Step 4：运行测试并确认 GREEN**

Run:

```bash
pytest -q tests/pipeline/test_runtime_modes.py
```

Expected: `8 passed`（参数化非法值计为 4 个测试用例）。

- [ ] **Step 5：提交运行模式改动**

```bash
git add config/settings.yaml src/novel_material/pipeline/runtime_modes.py tests/pipeline/test_runtime_modes.py
git commit -m "feat(insights): 配置标准模式章节上限" -m "主要改动：
- 增加 standard 自动 insights 的章节上限配置。
- 为运行模式补充上限字段及非法配置校验。

验证结果：
- pytest -q tests/pipeline/test_runtime_modes.py 通过。"
```

### Task 2：让 full 与 continue 传递模式范围

**Files:**
- Create: `tests/cli/test_pipeline_common.py`
- Modify: `src/novel_material/cli/pipeline_common.py`

- [ ] **Step 1：先写编排范围失败测试**

创建 `tests/cli/test_pipeline_common.py`：

```python
"""完整流水线统一阶段计划测试。"""

from novel_material.cli import pipeline_common
from novel_material.pipeline.orchestrator import RunRequest
from novel_material.runtime.contracts import RunStatus, StageResult


def _record_insights_call(monkeypatch, *, mode: str) -> dict:
    recorded = {}

    def fake_run_insights_stage(material_id, **kwargs):
        recorded.update(material_id=material_id, **kwargs)
        return StageResult(
            stage_id="stage-insights",
            name="insights",
            status=RunStatus.SUCCESS,
        )

    monkeypatch.setattr(
        pipeline_common,
        "run_insights_stage",
        fake_run_insights_stage,
    )
    spec = next(
        stage
        for stage in pipeline_common._stage_specs("nm_demo", {"mode": mode})
        if stage.name == "insights"
    )
    request = RunRequest(
        run_id="run-test",
        command="pipeline full",
        material_id="nm_demo",
    )
    assert spec.enabled(request) is True
    spec.execute(request)
    return recorded


def test_standard_pipeline_limits_automatic_insights_to_first_100(monkeypatch):
    monkeypatch.setattr(
        pipeline_common,
        "get_runtime_mode",
        lambda _name: type(
            "Mode",
            (),
            {"include_core_insights": True, "core_insight_chapter_limit": 100},
        )(),
    )

    recorded = _record_insights_call(monkeypatch, mode="standard")

    assert recorded == {
        "material_id": "nm_demo",
        "start_ch": 1,
        "end_ch": 100,
        "provider": None,
    }


def test_deep_pipeline_keeps_automatic_core_insights_unbounded(monkeypatch):
    monkeypatch.setattr(
        pipeline_common,
        "get_runtime_mode",
        lambda _name: type(
            "Mode",
            (),
            {"include_core_insights": True, "core_insight_chapter_limit": None},
        )(),
    )

    recorded = _record_insights_call(monkeypatch, mode="deep")

    assert recorded == {
        "material_id": "nm_demo",
        "start_ch": None,
        "end_ch": None,
        "provider": None,
    }


def test_explicit_pipeline_range_overrides_standard_default(monkeypatch):
    monkeypatch.setattr(
        pipeline_common,
        "get_runtime_mode",
        lambda _name: type(
            "Mode",
            (),
            {"include_core_insights": True, "core_insight_chapter_limit": 100},
        )(),
    )
    recorded = {}

    def fake_run_insights_stage(material_id, **kwargs):
        recorded.update(material_id=material_id, **kwargs)
        return StageResult(
            stage_id="stage-insights",
            name="insights",
            status=RunStatus.SUCCESS,
        )

    monkeypatch.setattr(
        pipeline_common,
        "run_insights_stage",
        fake_run_insights_stage,
    )
    options = {"mode": "standard", "start": 300, "end": 350}
    spec = next(
        stage
        for stage in pipeline_common._stage_specs("nm_demo", options)
        if stage.name == "insights"
    )
    spec.execute(
        RunRequest(
            run_id="run-test",
            command="pipeline continue",
            material_id="nm_demo",
        )
    )

    assert recorded["start_ch"] == 300
    assert recorded["end_ch"] == 350
```

- [ ] **Step 2：运行测试并确认 RED**

Run:

```bash
pytest -q tests/cli/test_pipeline_common.py
```

Expected: FAIL，记录参数中缺少 `start_ch` 和 `end_ch`。

- [ ] **Step 3：实现统一阶段范围传递**

在 `src/novel_material/cli/pipeline_common.py::_stage_specs` 中只解析一次模式，并计算自动范围：

```python
def _stage_specs(material_id: str, options: dict) -> tuple[StageSpec, ...]:
    provider = options.get("provider")
    runtime_mode = get_runtime_mode(options.get("mode", "standard"))
    insight_limit = runtime_mode.core_insight_chapter_limit
    has_explicit_range = options.get("start") is not None or options.get("end") is not None
    if has_explicit_range:
        insight_start = options.get("start")
        insight_end = options.get("end")
    else:
        insight_start = 1 if insight_limit is not None and insight_limit > 0 else None
        insight_end = insight_limit
```

把 insights `StageSpec` 改为：

```python
        StageSpec(
            "insights",
            lambda _request: run_insights_stage(
                material_id,
                start_ch=insight_start,
                end_ch=insight_end,
                provider=provider,
            ),
            blocking=False,
            enabled=lambda _request: runtime_mode.include_core_insights,
        ),
```

- [ ] **Step 4：运行编排器测试并确认 GREEN**

Run:

```bash
pytest -q tests/cli/test_pipeline_common.py tests/pipeline/test_runtime_modes.py
```

Expected: 全部 PASS。

- [ ] **Step 5：运行已有流水线契约回归测试**

Run:

```bash
pytest -q tests/cli/test_pipeline_contract.py tests/pipeline/test_stage_contracts.py tests/pipeline/test_insights_pipeline.py
```

Expected: 全部 PASS，且没有真实 LLM 或数据库调用。

- [ ] **Step 6：提交编排器改动**

```bash
git add src/novel_material/cli/pipeline_common.py tests/cli/test_pipeline_common.py
git commit -m "fix(insights): 限制标准流水线自动分析范围" -m "主要改动：
- full 与 continue 共用运行模式的 insights 章节范围。
- standard 默认传入前 100 章，显式 start/end 覆盖默认值，deep 保持全量。

验证结果：
- 流水线编排、阶段契约和 insights 单元测试通过。"
```

### Task 3：锁定独立 insights 命令的显式范围

**Files:**
- Modify: `tests/cli/test_command_contracts.py`

- [ ] **Step 1：添加独立命令回归测试**

在 `tests/cli/test_command_contracts.py` 增加导入：

```python
from novel_material.runtime.contracts import RunStatus, StageResult
```

该文件已有相同导入时不要重复。追加测试：

```python
def test_standalone_insights_keeps_explicit_chapter_range(tmp_path, monkeypatch):
    material_id = "nm_demo"
    novel_dir = tmp_path / material_id
    novel_dir.mkdir()
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 1\n  title: 第一章\n"
        "- chapter: 2\n  title: 第二章\n"
        "- chapter: 3\n  title: 第三章\n",
        encoding="utf-8",
    )
    recorded = {}

    def fake_generate(material_id_arg, **kwargs):
        recorded.update(material_id=material_id_arg, **kwargs)
        return StageResult(
            stage_id="stage-insights",
            name="insights",
            status=RunStatus.SUCCESS,
        )

    monkeypatch.setattr("novel_material.cli.pipeline.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.cli.pipeline.generate_chapter_insights",
        fake_generate,
    )

    result = runner.invoke(
        app,
        ["pipeline", "insights", material_id, "--start", "2", "--end", "3"],
    )

    assert result.exit_code == 0
    assert recorded["material_id"] == material_id
    assert recorded["start_ch"] == 2
    assert recorded["end_ch"] == 3
```

- [ ] **Step 2：运行测试并确认当前行为 GREEN**

Run:

```bash
pytest -q tests/cli/test_command_contracts.py::test_standalone_insights_keeps_explicit_chapter_range
```

Expected: PASS。该测试是对明确保留行为的特征锁定，因此无需人为制造失败，也不修改生产代码。

- [ ] **Step 3：提交回归测试**

```bash
git add tests/cli/test_command_contracts.py
git commit -m "test(insights): 锁定独立命令章节范围" -m "主要改动：
- 验证独立 insights 命令继续传递显式 start/end。

验证结果：
- 独立命令契约测试通过。"
```

### Task 4：更新用户与架构文档

**Files:**
- Modify: `docs/USER_MANUAL.md`
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1：更新用户手册的运行模式表格和说明**

将 `docs/USER_MANUAL.md` 的运行模式表格调整为：

```markdown
| 模式 | 目标 | insights 行为 |
|---|---|---|
| `fast` | 优先完成基础素材 | 跳过 core insights |
| `standard` | 默认无人值守 | 默认分析开头 100 章，可通过 `INSIGHTS_STANDARD_CHAPTER_LIMIT` 调整 |
| `deep` | 质量优先 | 全量执行 core insights，并保留关键章节深度分析扩展点 |
```

在独立 insights 命令说明后补充：

```markdown
上述 `standard` 上限只作用于未显式提供范围的 `full` 和 `continue` 自动编排；传入 `--start/--end` 时用户范围覆盖默认上限。独立执行 `nm pipeline insights` 时，不指定范围仍表示全量；指定 `--start/--end` 时严格使用用户范围。`refine` 继续基于全部 L1 章级分析数据运行。
```

- [ ] **Step 2：更新架构文档的数据流边界**

把 `ARCHITECTURE.md` 中原有运行模式段落更新为：

```markdown
`fast` 模式跳过 insights；`standard` 模式默认只为开头 100 章生成 core insights，上限由 `INSIGHTS_STANDARD_CHAPTER_LIMIT` 配置；`deep` 当前仍对全部已分析章节调用同一个 core insight 生成器。`full/continue --start/--end` 的显式用户范围覆盖模式默认范围。`deep` 的关键章节比例与阻断语义只是扩展元数据，尚无独立 deep 分析实现，文档和 Agent 不得声称已经完成更深层分析。该自动上限不影响独立 `nm pipeline insights --start/--end`，也不缩小 `refine` 的全书 L1 输入范围。
```

- [ ] **Step 3：检查文档差异和格式**

Run:

```bash
git diff --check -- docs/USER_MANUAL.md ARCHITECTURE.md config/settings.yaml
rg -n "INSIGHTS_STANDARD_CHAPTER_LIMIT|standard.*100|refine.*全书" docs/USER_MANUAL.md ARCHITECTURE.md config/settings.yaml
```

Expected: `git diff --check` 无输出；`rg` 在三个文件中命中新规则且表述一致。

- [ ] **Step 4：提交文档改动**

```bash
git add docs/USER_MANUAL.md ARCHITECTURE.md
git commit -m "docs(insights): 说明标准模式分析边界" -m "主要改动：
- 说明 standard 自动分析前 100 章的配置方式。
- 区分自动编排、独立 insights 命令和全书 refine 范围。

验证结果：
- 文档格式检查和关键词一致性检查通过。"
```

### Task 5：执行完整验证

**Files:**
- Verify only

- [ ] **Step 1：运行定向测试**

```bash
pytest -q \
  tests/pipeline/test_runtime_modes.py \
  tests/cli/test_pipeline_common.py \
  tests/cli/test_command_contracts.py \
  tests/cli/test_pipeline_contract.py \
  tests/pipeline/test_stage_contracts.py \
  tests/pipeline/test_insights_pipeline.py
```

Expected: 全部 PASS，无真实 LLM 或数据库调用。

- [ ] **Step 2：运行全量测试**

```bash
pytest -q
```

Expected: 0 failed；若存在项目既有跳过项，记录 skip 数量但不视为失败。

- [ ] **Step 3：验证 CLI 帮助与代码编译**

```bash
python -m novel_material.cli.main pipeline full --help
python -m novel_material.cli.main pipeline insights --help
python -m compileall -q src tests
```

Expected: 两个帮助命令退出码为 0；`compileall` 无输出并退出 0。

- [ ] **Step 4：确认只包含预期差异**

```bash
git status --short
git diff --check
git diff --stat HEAD~4..HEAD
```

Expected: 用户原有 `docs/feedback.md` 修改保持未提交；本功能提交只涉及计划列出的配置、源码、测试和文档文件。

- [ ] **Step 5：记录最终验证提交（仅在验证需要补充文档时）**

如果所有验证均通过且没有新文件需要修改，不创建空提交。若需要补充验证记录，只修改本计划的执行状态并使用：

```bash
git add docs/superpowers/plans/2026-06-23-standard-insights-chapter-limit.md
git commit -m "docs(plan): 记录 insights 上限验证结果" -m "主要改动：
- 记录定向测试、全量测试和 CLI 检查结果。

验证结果：
- 全部计划验证命令通过。"
```
