# 前置导航与人物小传 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `evaluation.yaml` 升级为可复用的前置全局导航，并为自适应筛选出的主要人物生成完整小传，同时解除 `--window` 与 evaluate 的隐式绑定。

**Architecture:** 第二期在现有 YAML 事实层上增加稳定的 navigation 读取适配器、人物候选评分与完整小传契约。`evaluate` 写入 `schema_version: 3.0.0`，旧 `2.0.1` 通过读取端适配，不自动迁移；`characters` 消费前置导航和章级事实，先确定 5–12 名主要人物，再只对这些人物生成完整小传，其余人物保留简档。Pipeline 编排中 `--window` 只控制章级前后文窗口，前置导航由运行模式和显式开关控制。

**Tech Stack:** Python 3.10+、Pydantic v2、Typer、PyYAML、pytest、现有 runtime/audit/reporting 事件与报告层。

---

## 现有设计来源

- 总体设计：`docs/superpowers/specs/2026-06-23-layered-analysis-and-quality-report-design.md` 的第 5、6、11、13、14、15、16 节。
- 第一期延期边界：`docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md` 中明确延期的 `evaluation.yaml 3.0.0`、`--window` 解耦、5–12 名主要人物选择与完整小传、正式性能门禁。
- 第一期执行状态：`docs/superpowers/execution/2026-06-23-artifact-audit-report/STATE.md`，当前第一期已完成。

## 实施边界

- 本计划只实施第二期“前置导航与人物小传”。
- 不实施分层世界观、实体关系、`work_profile.yaml`、存储/搜索适配；这些属于第三期。
- 不修改真实 `data/novels/` 事实文件；真实素材只作为显式 smoke test 的只读输入，或在用户另行授权后生成新运行。
- 不修改用户当前未提交的 `docs/feedback.md`。
- 默认测试不得调用真实 LLM、embedding、PostgreSQL、storage sync 或数据库 migration。
- 新代码必须保持第一期审计、报告、run logging 与终端摘要的依赖边界。
- 旧 `evaluation.yaml` 只在读取端兼容，不在读取时自动改写。
- 主要人物完整小传允许 LLM 失败，但失败不得被伪装成成功完整小传；若兜底发生，审计继续产生 `character_profile_fallback`。
- 在人工检索基线完成前，不声称新结构提升检索质量。

## 第二期核心决策

### 1. 前置导航与 `--window` 解耦

- `evaluate` 的职责改为生成前置全局导航。
- `--window` 只控制章级分析是否使用前章摘要、当前章和下章预览。
- `analyze --window` 不再因为缺少 `evaluation.yaml` 直接失败；若导航缺失，章级分析仍可运行，并记录“无前置导航”的降级上下文。
- `pipeline full --mode standard|deep` 默认运行前置导航；`fast` 默认跳过。
- 新增 `--skip-navigation`：允许 `standard/deep` 跳过前置导航，用于省时或从旧素材继续。
- 新增 `--navigation`：允许 `fast` 显式启用前置导航。
- `pipeline continue` 依据状态与产物契约恢复，不能再用“是否传了 `--window`”推断 evaluate 是否应存在。

### 2. `evaluation.yaml` 3.0.0 只表达“导航”

新写入格式：

```yaml
schema_version: 3.0.0
novel_type: []
premise: ""
main_thread_summary: ""
stage_map:
  - stage: opening
    chapter_ranges: [[1, 80]]
    central_conflict: ""
    turning_points:
      - chapter: 12
        event: ""
core_character_candidates:
  - name: ""
    reasons: []
    confidence: 0.0
worldbuilding_dimensions: []
analysis_focus: []
sample_coverage:
  sampled_chapters: []
  covered_ranges: []
  limitations: []
evaluation_timestamp: ""
```

`stage_map` 和 `core_character_candidates` 是采样推断，不冒充完整章级事实。读取端将旧 `2.0.1` 的 `stage_summaries`、`core_characters_hint` 映射为低置信度导航对象。

### 3. 人物选择不再只看出场次数

选择器综合：

- 前置导航中的核心人物候选与置信度。
- 出场频率。
- 贯穿范围。
- 关键事件参与度。
- 关系中心度。
- 已知 role 或叙事功能信号。

合格候选不少于 5 人时，完整小传覆盖 5–12 人；不足 5 人时覆盖全部合格候选并记录原因。其余人物生成简档，不无限扩大 LLM 请求。

## 文件结构与职责

### 新建文件

```text
src/novel_material/pipeline/evaluation_models.py
  # evaluation 3.0.0 Pydantic 模型、旧版适配器、只读加载入口。

src/novel_material/pipeline/characters_selection.py
  # 人物候选评分、5–12 名完整小传选择、选择原因与审计元数据。

src/novel_material/pipeline/characters_biography.py
  # 完整小传字段契约、LLM 响应规范化、兜底检测辅助。

tests/pipeline/test_evaluation_models.py
tests/pipeline/test_evaluation_v3.py
tests/pipeline/test_navigation_window_decoupling.py
tests/pipeline/test_character_selection.py
tests/pipeline/test_character_biography.py
tests/cli/test_character_repair_contract.py
```

### 修改文件

- `src/novel_material/pipeline/evaluate.py`：写入 v3 导航、生成 sample coverage、保留断点续传。
- `src/novel_material/pipeline/analyze_context.py` / `analyze.py`：消费导航但不依赖 `--window` 隐式触发。
- `src/novel_material/cli/pipeline_common.py`：阶段计划从 `use_window` 改为 `use_navigation`。
- `src/novel_material/cli/pipeline.py`：公开 `--navigation/--skip-navigation`，更新 `analyze/full/continue/status` 文案。
- `src/novel_material/pipeline/progress.py` / `state.py`：识别 v3 evaluation 与 continue 阶段。
- `src/novel_material/pipeline/characters_core.py`：接入自适应选择、完整小传、定向修复。
- `src/novel_material/pipeline/characters_layer.py`：核心人物 prompt 改为完整小传契约，支持只处理指定名单。
- `src/novel_material/pipeline/characters_profile.py`：保存完整小传与简档，避免主要人物兜底被标成功。
- `src/novel_material/pipeline/characters_selector.py`：保留旧入口兼容，委托新选择器。
- `src/novel_material/prompts/evaluate.yaml`、`src/novel_material/prompts/characters.yaml`：同步 v3 输出契约。
- `src/novel_material/schema/fields.yaml`：集中配置人物选择数量、评分权重、导航字段长度。
- `src/novel_material/validation/models.py`、`validation/validators.py`：兼容校验 v2 与 v3。
- `src/novel_material/audit/rules.py`：主要人物完整小传字段缺失继续 error，使用新选择元数据提升准确性。
- `src/novel_material/reporting/builder.py`、`markdown.py`：报告新增完整小传通过数量、简档数量和失败原因。
- `ARCHITECTURE.md`、`docs/USER_MANUAL.md`、`docs/REQUIREMENTS.md`、`docs/README.md`：同步第二期行为与限制。

## Task 1：建立 evaluation 3.0.0 模型与旧版适配器

**Files:**
- Create: `src/novel_material/pipeline/evaluation_models.py`
- Create: `tests/pipeline/test_evaluation_models.py`
- Modify: `src/novel_material/validation/models.py`
- Modify: `src/novel_material/validation/validators.py`

- [ ] **Step 1: 编写 v3 模型与 v2 适配失败测试**

```python
from pathlib import Path

import yaml

from novel_material.pipeline.evaluation_models import (
    EvaluationNavigation,
    load_evaluation_navigation,
    normalize_evaluation_navigation,
)


def write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")


def test_v3_navigation_keeps_stage_map_candidates_and_sample_coverage():
    navigation = normalize_evaluation_navigation(
        {
            "schema_version": "3.0.0",
            "novel_type": ["都市"],
            "premise": "重生者在商业与情感之间重新选择。",
            "main_thread_summary": "主角重回青春时期，通过商业机会和关系重建改变命运。",
            "stage_map": [
                {
                    "stage": "opening",
                    "chapter_ranges": [[1, 20]],
                    "central_conflict": "主角决定改变过去。",
                    "turning_points": [{"chapter": 8, "event": "第一次主动破局"}],
                }
            ],
            "core_character_candidates": [
                {
                    "name": "陈汉升",
                    "reasons": ["贯穿全书", "推动主线"],
                    "confidence": 0.96,
                }
            ],
            "worldbuilding_dimensions": ["商业环境", "校园关系"],
            "analysis_focus": ["人物选择代价", "创业节奏"],
            "sample_coverage": {
                "sampled_chapters": [1, 8, 20],
                "covered_ranges": [[1, 20]],
                "limitations": ["仅基于采样章节推断"],
            },
        }
    )

    assert isinstance(navigation, EvaluationNavigation)
    assert navigation.schema_version == "3.0.0"
    assert navigation.core_character_candidates[0].name == "陈汉升"
    assert navigation.sample_coverage.sampled_chapters == (1, 8, 20)


def test_legacy_v201_is_adapted_without_rewriting_file(tmp_path: Path):
    novel_dir = tmp_path / "nm_demo"
    evaluation_path = novel_dir / "evaluation.yaml"
    write_yaml(
        evaluation_path,
        {
            "schema_version": "2.0.1",
            "novel_type": ["都市"],
            "main_thread_summary": "旧版主线概要。",
            "total_chapters": 100,
            "core_characters_hint": ["陈汉升"],
            "stage_summaries": {1: "开篇", 2: "发展", 3: "转折", 4: "高潮", 5: "收束"},
        },
    )

    before = evaluation_path.read_text(encoding="utf-8")
    navigation = load_evaluation_navigation(novel_dir)
    after = evaluation_path.read_text(encoding="utf-8")

    assert navigation.schema_version == "3.0.0"
    assert navigation.source_schema_version == "2.0.1"
    assert navigation.core_character_candidates[0].confidence == 0.5
    assert before == after
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/pipeline/test_evaluation_models.py -v`

Expected: FAIL，提示 `novel_material.pipeline.evaluation_models` 不存在。

- [ ] **Step 3: 实现 v3 模型、字段校验与旧版适配器**

实现要点：

```python
class TurningPoint(BaseModel):
    chapter: int = Field(ge=1)
    event: str = Field(min_length=1)


class StageMapItem(BaseModel):
    stage: str = Field(min_length=1)
    chapter_ranges: tuple[tuple[int, int], ...] = ()
    central_conflict: str = ""
    turning_points: tuple[TurningPoint, ...] = ()


class CoreCharacterCandidate(BaseModel):
    name: str = Field(min_length=1)
    reasons: tuple[str, ...] = ()
    confidence: float = Field(ge=0, le=1)


class SampleCoverage(BaseModel):
    sampled_chapters: tuple[int, ...] = ()
    covered_ranges: tuple[tuple[int, int], ...] = ()
    limitations: tuple[str, ...] = ()


class EvaluationNavigation(BaseModel):
    schema_version: Literal["3.0.0"] = "3.0.0"
    source_schema_version: str = "3.0.0"
    novel_type: tuple[str, ...] = ()
    premise: str = ""
    main_thread_summary: str = ""
    stage_map: tuple[StageMapItem, ...] = ()
    core_character_candidates: tuple[CoreCharacterCandidate, ...] = ()
    worldbuilding_dimensions: tuple[str, ...] = ()
    analysis_focus: tuple[str, ...] = ()
    sample_coverage: SampleCoverage = Field(default_factory=SampleCoverage)
    evaluation_timestamp: str | None = None
```

`normalize_evaluation_navigation(payload)`：

- `schema_version == "3.0.0"`：按 v3 解析。
- `schema_version == "2.0.1"` 或缺失但含 `stage_summaries/core_characters_hint`：适配为 v3。
- 旧 `stage_summaries` 映射为 `stage_map`，stage 名称按 `opening/development/turning/climax/resolution`。
- 旧 `core_characters_hint` 映射为 `confidence=0.5`、`reasons=("legacy_core_characters_hint",)`。
- 不在此函数写文件。

- [ ] **Step 4: 更新 validation 兼容测试**

在 `tests/validation/test_schema.py` 或新文件中加入：

```python
def test_validation_accepts_evaluation_v3_navigation():
    model = EvaluationModel(
        schema_version="3.0.0",
        novel_type=["都市"],
        premise="重生者重新选择人生。",
        main_thread_summary="主角围绕事业与关系重建展开主线。",
        stage_map=[],
        core_character_candidates=[],
        worldbuilding_dimensions=[],
        analysis_focus=[],
        sample_coverage={"sampled_chapters": [], "covered_ranges": [], "limitations": []},
    )
    assert model.schema_version == "3.0.0"
```

- [ ] **Step 5: 运行定向测试**

Run:

```bash
python -m pytest tests/pipeline/test_evaluation_models.py tests/validation/test_schema.py -v
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/pipeline/evaluation_models.py src/novel_material/validation/models.py src/novel_material/validation/validators.py tests/pipeline/test_evaluation_models.py tests/validation/test_schema.py
git commit -m "feat(evaluation): 增加前置导航模型兼容读取" -m "主要改动：
- 新增 evaluation 3.0.0 前置导航模型
- 增加 2.0.1 evaluation.yaml 只读适配器
- 更新 validation 兼容 v2 与 v3

验证结果：
- python -m pytest tests/pipeline/test_evaluation_models.py tests/validation/test_schema.py -v：通过"
```

## Task 2：让 evaluate 写入 3.0.0 前置导航

**Files:**
- Modify: `src/novel_material/pipeline/evaluate.py`
- Modify: `src/novel_material/prompts/evaluate.yaml`
- Create: `tests/pipeline/test_evaluation_v3.py`

- [ ] **Step 1: 编写 normalize 与 sample coverage 测试**

```python
from novel_material.pipeline.evaluate import (
    build_sample_coverage,
    normalize_evaluation_response,
)


def test_normalize_evaluation_response_requires_v3_navigation_fields():
    result = normalize_evaluation_response(
        {
            "novel_type": ["都市"],
            "premise": "重生者重新选择人生。",
            "main_thread_summary": "主角围绕事业与关系重建展开主线。",
            "stage_map": [
                {
                    "stage": "opening",
                    "chapter_ranges": [[1, 10]],
                    "central_conflict": "主角重新面对旧关系。",
                    "turning_points": [{"chapter": 3, "event": "首次主动改变"}],
                }
            ],
            "core_character_candidates": [
                {"name": "陈汉升", "reasons": ["贯穿主线"], "confidence": 0.9}
            ],
            "worldbuilding_dimensions": ["校园", "商业"],
            "analysis_focus": ["人物选择", "创业节奏"],
        }
    )

    assert result["schema_version"] == "3.0.0"
    assert result["core_character_candidates"][0]["confidence"] == 0.9


def test_build_sample_coverage_records_sampled_chapters_and_limitations():
    batches = {
        1: [{"chapter": 1}, {"chapter": 10}],
        2: [{"chapter": 30}],
    }
    coverage = build_sample_coverage(batches, total_chapters=100)

    assert coverage["sampled_chapters"] == [1, 10, 30]
    assert coverage["covered_ranges"] == [[1, 30]]
    assert coverage["limitations"]
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/pipeline/test_evaluation_v3.py -v`

Expected: FAIL，提示 v3 字段或 `build_sample_coverage` 不存在。

- [ ] **Step 3: 修改 evaluate prompt 与响应规范化**

要求：

- `_SYSTEM_PROMPT` 改为“前置全局导航助手”。
- `_EVALUATION_JSON_SCHEMA` 必须包含 v3 字段。
- `normalize_evaluation_response()` 输出总是带 `schema_version: "3.0.0"`。
- 不再只要求 `core_characters_hint` 字符串列表；改为 `core_character_candidates` 对象列表。
- `stage_map` 的 `chapter_ranges` 必须是 `[start, end]` 二元列表，非法响应抛 `LLMResponseContractError`。

- [ ] **Step 4: 修改进度合并与最终写入**

要求：

- `load_evaluation_progress()` 默认字段改为 v3。
- 每批结果合并：
  - `novel_type` 去重保序，最多 3。
  - `core_character_candidates` 按 name 去重，保留较高 confidence 与合并 reasons。
  - `stage_map` 追加并按章节范围起点排序。
  - `analysis_focus/worldbuilding_dimensions` 去重保序。
- 最终写入 `evaluation.yaml` 使用 v3 字段，包含 `sample_coverage`。
- 保留 `_evaluation_progress.yaml` 断点续传语义。

- [ ] **Step 5: 运行定向测试**

Run:

```bash
python -m pytest tests/pipeline/test_evaluation_models.py tests/pipeline/test_evaluation_v3.py tests/pipeline/test_llm_response_contracts.py -v
```

Expected: 全部通过。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/pipeline/evaluate.py src/novel_material/prompts/evaluate.yaml tests/pipeline/test_evaluation_v3.py tests/pipeline/test_llm_response_contracts.py
git commit -m "feat(evaluation): 输出前置导航三点零" -m "主要改动：
- 将 evaluate 输出升级为 schema_version 3.0.0
- 增加 stage_map、core_character_candidates 与 sample_coverage
- 更新 LLM 响应契约测试

验证结果：
- python -m pytest tests/pipeline/test_evaluation_models.py tests/pipeline/test_evaluation_v3.py tests/pipeline/test_llm_response_contracts.py -v：通过"
```

## Task 3：解除 `--window` 与前置导航绑定

**Files:**
- Modify: `src/novel_material/cli/pipeline_common.py`
- Modify: `src/novel_material/cli/pipeline.py`
- Modify: `src/novel_material/pipeline/analyze_context.py`
- Modify: `tests/cli/test_pipeline_common.py`
- Create: `tests/pipeline/test_navigation_window_decoupling.py`

- [ ] **Step 1: 编写阶段计划测试**

```python
from novel_material.cli import pipeline_common


def stage_names(options: dict) -> list[str]:
    return [item.name for item in pipeline_common._stage_specs("nm_demo", options)]


def test_standard_full_runs_navigation_without_window():
    specs = pipeline_common._stage_specs("nm_demo", {"mode": "standard"})
    evaluation = next(item for item in specs if item.name == "evaluation")
    assert evaluation.enabled(None) is True


def test_fast_skips_navigation_unless_explicit():
    skipped = next(
        item for item in pipeline_common._stage_specs("nm_demo", {"mode": "fast"})
        if item.name == "evaluation"
    )
    enabled = next(
        item for item in pipeline_common._stage_specs("nm_demo", {"mode": "fast", "use_navigation": True})
        if item.name == "evaluation"
    )
    assert skipped.enabled(None) is False
    assert enabled.enabled(None) is True


def test_window_no_longer_controls_evaluation_stage():
    specs = pipeline_common._stage_specs("nm_demo", {"mode": "fast", "use_window": True})
    evaluation = next(item for item in specs if item.name == "evaluation")
    assert evaluation.enabled(None) is False
```

- [ ] **Step 2: 编写 analyze 缺失导航不失败测试**

在 `tests/pipeline/test_navigation_window_decoupling.py` 中模拟 `analyze_context`：

```python
def test_analyze_context_allows_window_without_navigation(tmp_path, monkeypatch):
    # 构造无 evaluation.yaml 的素材目录
    # 调用本 Task 新增的 load_optional_navigation_context(novel_dir)
    # 断言返回空导航文本和 diagnostic code navigation_missing，而不是抛异常
```

本 Task 必须在 `src/novel_material/pipeline/analyze_context.py` 中新增 `load_optional_navigation_context(novel_dir: Path) -> tuple[str, tuple[str, ...]]`，返回 `(context_text, diagnostic_codes)`；测试必须直接调用这个 helper。

- [ ] **Step 3: 运行测试并确认失败**

Run:

```bash
python -m pytest tests/cli/test_pipeline_common.py tests/pipeline/test_navigation_window_decoupling.py -v
```

Expected: FAIL，当前 evaluation 仍由 `use_window` 控制，CLI 仍要求 `--window` 前必须有 evaluation。

- [ ] **Step 4: 修改阶段选项解析**

在 `pipeline_common.py` 新增：

```python
def _use_navigation(options: dict) -> bool:
    if options.get("use_navigation") is True:
        return True
    if options.get("skip_navigation") is True:
        return False
    return get_runtime_mode(options.get("mode", "standard")).name in {"standard", "deep"}
```

`StageSpec("evaluation")` 的 `enabled` 改为 `_use_navigation(options)`，不再读取 `use_window`。

- [ ] **Step 5: 修改 CLI 参数与文案**

- `full` 增加 `--navigation/--skip-navigation`。
- `continue` 增加同样开关。
- `analyze --window` 删除“必须先运行 evaluate”的硬失败；改为提示“若存在 evaluation.yaml 将消费前置导航”。
- 旧 help 文案“自动执行总体评估”改为“前置导航由运行模式或 --navigation 控制”。

- [ ] **Step 6: 运行 CLI 契约测试**

Run:

```bash
python -m pytest tests/cli/test_pipeline_common.py tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/pipeline/test_navigation_window_decoupling.py -v
python -m novel_material.cli.main pipeline full --help
python -m novel_material.cli.main pipeline analyze --help
```

Expected:

- pytest 全部通过。
- `full --help` 显示 `--navigation` 与 `--skip-navigation`。
- `analyze --help` 不再声称 `--window` 需要先 evaluate。

- [ ] **Step 7: 提交**

```bash
git add src/novel_material/cli/pipeline_common.py src/novel_material/cli/pipeline.py src/novel_material/pipeline/analyze_context.py tests/cli/test_pipeline_common.py tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/pipeline/test_navigation_window_decoupling.py
git commit -m "feat(pipeline): 解耦前置导航与滑动窗口" -m "主要改动：
- 前置导航阶段改由运行模式和显式开关控制
- --window 只控制章级前后文窗口
- analyze 在缺少 evaluation.yaml 时不再直接失败

验证结果：
- python -m pytest tests/cli/test_pipeline_common.py tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/pipeline/test_navigation_window_decoupling.py -v：通过
- pipeline full/analyze help 检查通过"
```

## Task 4：实现自适应人物选择器

**Files:**
- Create: `src/novel_material/pipeline/characters_selection.py`
- Modify: `src/novel_material/pipeline/characters_selector.py`
- Modify: `src/novel_material/schema/fields.yaml`
- Create: `tests/pipeline/test_character_selection.py`

- [ ] **Step 1: 编写 5–12 名选择与不足 5 人测试**

```python
from novel_material.pipeline.characters_selection import (
    CharacterSignals,
    select_biography_targets,
)
from novel_material.pipeline.evaluation_models import CoreCharacterCandidate, EvaluationNavigation


def test_selects_between_five_and_twelve_when_enough_candidates():
    appearance = {f"角色{i}": 100 - i for i in range(1, 20)}
    navigation = EvaluationNavigation(
        core_character_candidates=(
            CoreCharacterCandidate(name="角色15", reasons=("导航候选",), confidence=0.99),
        )
    )
    signals = CharacterSignals(
        appearance_counts=appearance,
        chapter_span={name: (1, 100) for name in appearance},
        key_event_counts={name: 3 for name in appearance},
        relationship_degree={name: 1 for name in appearance},
        navigation=navigation,
    )

    result = select_biography_targets(signals)

    assert 5 <= len(result.targets) <= 12
    assert "角色15" in [item.name for item in result.targets]
    assert result.selection_reason == "enough_candidates"


def test_selects_all_qualified_when_less_than_five():
    signals = CharacterSignals(
        appearance_counts={"甲": 20, "乙": 12, "丙": 6},
        chapter_span={"甲": (1, 20), "乙": (3, 18), "丙": (8, 14)},
        key_event_counts={"甲": 2, "乙": 1, "丙": 1},
        relationship_degree={"甲": 1, "乙": 1, "丙": 0},
        navigation=EvaluationNavigation(),
    )

    result = select_biography_targets(signals)

    assert [item.name for item in result.targets] == ["甲", "乙", "丙"]
    assert result.selection_reason == "fewer_than_minimum"
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/pipeline/test_character_selection.py -v`

Expected: FAIL，模块不存在。

- [ ] **Step 3: 实现信号模型与评分**

实现：

```python
@dataclass(frozen=True)
class CharacterSignals:
    appearance_counts: dict[str, int]
    chapter_span: dict[str, tuple[int, int]]
    key_event_counts: dict[str, int]
    relationship_degree: dict[str, int]
    navigation: EvaluationNavigation


@dataclass(frozen=True)
class BiographyTarget:
    name: str
    score: float
    reasons: tuple[str, ...]
    appearance_count: int
    role_hint: str = "supporting"


@dataclass(frozen=True)
class BiographySelection:
    targets: tuple[BiographyTarget, ...]
    selection_reason: str
    qualified_count: int
```

评分规则：

- 出场次数归一化权重 0.35。
- 贯穿范围权重 0.20。
- 关键事件参与权重 0.20。
- 关系中心度权重 0.10。
- 导航候选权重 0.15，乘以 confidence。
- 合格门槛使用 `character_thresholds.minor`。
- 数量范围从 `fields.yaml` 读取 `major_character_biography.min/max`，默认 5/12。

- [ ] **Step 4: 从 chapters_data 派生信号**

增加 `build_character_signals(chapters_data, navigation)`：

- `appearance_counts` 复用 `_extract_appearance_stats()`。
- `chapter_span` 记录首次和末次出场。
- `key_event_counts`：若 `key_event` 文本包含人物名则计数。
- `relationship_degree`：先用同章共现近似，后续人物关系网生成后再精化。

- [ ] **Step 5: 保留旧 `_select_candidate_characters` 兼容**

`characters_selector.py` 继续导出 `_select_candidate_characters()`，避免旧测试和调用方中断；新逻辑通过 `characters_selection.py` 使用。

- [ ] **Step 6: 运行测试**

Run:

```bash
python -m pytest tests/pipeline/test_character_selection.py tests/pipeline/test_llm_response_contracts.py -v
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add src/novel_material/pipeline/characters_selection.py src/novel_material/pipeline/characters_selector.py src/novel_material/schema/fields.yaml tests/pipeline/test_character_selection.py
git commit -m "feat(characters): 增加主要人物自适应选择器" -m "主要改动：
- 新增人物评分信号和完整小传目标选择
- 将完整小传数量限制集中配置为 5 到 12
- 保留旧统计分层选择入口兼容

验证结果：
- python -m pytest tests/pipeline/test_character_selection.py tests/pipeline/test_llm_response_contracts.py -v：通过"
```

## Task 5：定义完整小传契约与响应规范化

**Files:**
- Create: `src/novel_material/pipeline/characters_biography.py`
- Modify: `src/novel_material/pipeline/characters_layer.py`
- Modify: `src/novel_material/prompts/characters.yaml`
- Create: `tests/pipeline/test_character_biography.py`

- [ ] **Step 1: 编写完整小传字段测试**

```python
from novel_material.pipeline.characters_biography import normalize_biography_response


def test_normalize_biography_response_requires_full_profile_fields():
    result = normalize_biography_response(
        {
            "characters": [
                {
                    "name": "陈汉升",
                    "role": "protagonist",
                    "archetype": "重生创业者",
                    "moral_spectrum": "灰色",
                    "identity": "学生与创业者",
                    "life_summary": "重生后重新处理事业和关系。",
                    "external_goal": "抓住商业机会。",
                    "internal_need": "理解亲密关系中的责任。",
                    "fear": "重蹈覆辙。",
                    "fatal_flaw": "自负且逃避承诺。",
                    "contradiction": "精明外壳下仍有情感软肋。",
                    "arc_stages": [{"stage": "opening", "change": "主动破局", "evidence": {"chapters": [1]}}],
                    "relationships": [{"character": "沈幼楚", "dynamic": "守护与亏欠", "evidence": {"chapters": [2]}}],
                    "habits": ["嘴硬"],
                    "speech_style": "玩世不恭",
                    "interaction_patterns": ["以调侃化解压力"],
                    "key_scenes": [{"chapter": 1, "event": "重生醒来", "function": "确立新选择"}],
                    "craft_notes": [{"technique": "反差塑造", "boundary": "不可直接照搬人设"}],
                    "confidence": 0.86,
                    "basis": "inference",
                    "description": "核心人物完整小传。",
                    "arc_summary": "从重生后的功利选择走向承担关系代价。",
                    "psychology": {"motivation": "改变命运"},
                    "narrative_function": "推动主线",
                    "first_appearance_chapter": 1,
                    "key_events": [{"chapter": 1, "description": "重生"}],
                }
            ]
        },
        candidate_names={"陈汉升"},
    )

    profile = result[0]
    assert profile["profile_level"] == "full"
    assert profile["biography_complete"] is True
    assert profile["basis"] == "inference"
```

- [ ] **Step 2: 编写缺失必填字段失败测试**

```python
import pytest
from novel_material.infra.llm_contracts import LLMResponseContractError


def test_biography_response_rejects_missing_psychology_and_arc():
    with pytest.raises(LLMResponseContractError, match="arc_stages"):
        normalize_biography_response(
            {"characters": [{"name": "陈汉升", "role": "protagonist"}]},
            candidate_names={"陈汉升"},
        )
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/pipeline/test_character_biography.py -v`

Expected: FAIL，模块不存在。

- [ ] **Step 4: 实现完整小传规范化**

要求：

- `normalize_biography_response(payload, candidate_names)` 只接受候选名单内人物。
- 必填字段缺失抛 `LLMResponseContractError`。
- 输出继续保留旧消费字段：`description`、`arc_summary`、`psychology`、`relationships`、`key_events`。
- 新增：
  - `profile_level: "full"`
  - `biography_complete: true`
  - `identity/life_summary/external_goal/internal_need/fear/fatal_flaw/contradiction`
  - `arc_stages/interaction_patterns/key_scenes/craft_notes/confidence/basis`
- `basis` 只允许 `fact` 或 `inference`。

- [ ] **Step 5: 更新核心人物 prompt**

`characters.yaml` 与 `characters_layer.py` 的 core prompt 必须要求完整小传字段，并强调：

- 每项分析写 `fact` 或 `inference`。
- `key_scenes` 必须包含章节号。
- 不知道时写结构化不适用原因，不得留空。

- [ ] **Step 6: 运行定向测试**

Run:

```bash
python -m pytest tests/pipeline/test_character_biography.py tests/pipeline/test_llm_response_contracts.py -v
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add src/novel_material/pipeline/characters_biography.py src/novel_material/pipeline/characters_layer.py src/novel_material/prompts/characters.yaml tests/pipeline/test_character_biography.py tests/pipeline/test_llm_response_contracts.py
git commit -m "feat(characters): 定义主要人物完整小传契约" -m "主要改动：
- 新增完整小传响应规范化
- 扩展核心人物 prompt 字段
- 保留旧人物字段以兼容存储和检索

验证结果：
- python -m pytest tests/pipeline/test_character_biography.py tests/pipeline/test_llm_response_contracts.py -v：通过"
```

## Task 6：接入人物生成、简档与索引元数据

**Files:**
- Modify: `src/novel_material/pipeline/characters_core.py`
- Modify: `src/novel_material/pipeline/characters_profile.py`
- Modify: `tests/pipeline/test_character_selection.py`
- Create: `tests/pipeline/test_characters_pipeline_biographies.py`

- [ ] **Step 1: 编写 characters 阶段只为目标人物生成完整小传测试**

测试构造：

- `chapters.yaml` 中 8 名合格人物。
- `evaluation.yaml` v3 中强化其中 1 名导航候选。
- monkeypatch `_extract_character_batch`，记录 core 调用名单。
- 断言完整小传目标数量在 5–8，非目标人物仍写简档。

- [ ] **Step 2: 编写 `_index.yaml` 元数据测试**

断言 `characters/_index.yaml` 包含：

```yaml
biography_target_count: 5
biography_completed_count: 5
biography_failed_count: 0
biography_selection_reason: enough_candidates
biography_targets:
  - name: ""
    score: 0.0
    reasons: []
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python -m pytest tests/pipeline/test_characters_pipeline_biographies.py -v`

Expected: FAIL，当前 `generate_characters` 仍按 core/supporting/minor 三层批量处理。

- [ ] **Step 4: 修改 `generate_characters()` 流程**

新流程：

1. 加载章节数据。
2. `navigation = load_evaluation_navigation(novel_dir)`，缺失时使用空导航。
3. `signals = build_character_signals(chapters_data, navigation)`。
4. `selection = select_biography_targets(signals)`。
5. 对 `selection.targets` 调用完整小传 prompt。
6. 对其余合格人物生成简档，必要时可使用现有 supporting/minor prompt。
7. 写入 profile 文件时：
   - 完整小传：`profile_level=full`、`biography_complete=true`。
   - 简档：`profile_level=brief`、`biography_complete=false`。
   - 兜底：`profile_level=fallback`、`biography_complete=false`。
8. `_index.yaml` 写入完整小传统计与选择原因。

- [ ] **Step 5: 保持增量写入与断点续传**

- 已存在 `biography_complete=true` 的目标人物不重复调用 LLM。
- 已存在但不完整的目标人物应进入重建名单。
- 保存文件名策略不变，避免破坏已有读取。

- [ ] **Step 6: 运行测试**

Run:

```bash
python -m pytest tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_character_selection.py tests/pipeline/test_character_biography.py -v
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add src/novel_material/pipeline/characters_core.py src/novel_material/pipeline/characters_profile.py tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_character_selection.py
git commit -m "feat(characters): 接入主要人物完整小传生成" -m "主要改动：
- characters 阶段接入前置导航和自适应人物选择
- 主要人物生成完整小传，其余人物保留简档或兜底
- characters/_index.yaml 记录完整小传数量和选择原因

验证结果：
- python -m pytest tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_character_selection.py tests/pipeline/test_character_biography.py -v：通过"
```

## Task 7：增加定向人物修复 CLI

**Files:**
- Modify: `src/novel_material/cli/pipeline.py`
- Modify: `src/novel_material/pipeline/characters_core.py`
- Create: `tests/cli/test_character_repair_contract.py`

- [ ] **Step 1: 编写 CLI 契约测试**

```python
from typer.testing import CliRunner

from novel_material.cli.main import app


def test_characters_repair_character_option_is_repeatable(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_stage(material_id, **kwargs):
        captured.update(material_id=material_id, **kwargs)
        return True

    monkeypatch.setattr("novel_material.cli.pipeline.generate_characters", fake_stage)

    result = runner.invoke(
        app,
        [
            "pipeline",
            "characters",
            "nm_demo",
            "--repair-character",
            "陈汉升",
            "--repair-character",
            "沈幼楚",
        ],
    )

    assert result.exit_code == 0
    assert captured["repair_characters"] == ("陈汉升", "沈幼楚")
```

- [ ] **Step 2: 编写只重建指定人物测试**

在 pipeline 测试中构造已有 3 个 profile，调用 `generate_characters("nm_demo", provider=None, repair_characters=("甲",))`，断言只替换甲的 profile，其他文件 SHA-256 不变。

- [ ] **Step 3: 运行测试并确认失败**

Run:

```bash
python -m pytest tests/cli/test_character_repair_contract.py tests/pipeline/test_characters_pipeline_biographies.py -v
```

Expected: FAIL，CLI 暂不支持 `--repair-character`。

- [ ] **Step 4: 实现 `repair_characters` 参数**

- `cmd_characters()` 增加 `repair_character: list[str] = typer.Option(None, "--repair-character", help="只重建指定人物，可重复")`。
- `generate_characters(material_id, progress_callback=None, provider=None, repair_characters: tuple[str, ...] = ())`。
- 修复模式只选择指定人物；若指定人物不是合格候选，也允许生成完整小传，但在 `_index.yaml` 中记录 `repair_requested: true`。
- 修复前只删除或覆盖目标人物 profile，不动其他人物 profile。
- relationships/_index 重建时可读取所有现存 profile 重新汇总。

- [ ] **Step 5: 运行测试与 help**

Run:

```bash
python -m pytest tests/cli/test_character_repair_contract.py tests/pipeline/test_characters_pipeline_biographies.py -v
python -m novel_material.cli.main pipeline characters --help
```

Expected:

- pytest 通过。
- help 显示 `--repair-character`。

- [ ] **Step 6: 提交**

```bash
git add src/novel_material/cli/pipeline.py src/novel_material/pipeline/characters_core.py tests/cli/test_character_repair_contract.py tests/pipeline/test_characters_pipeline_biographies.py
git commit -m "feat(characters): 支持定向重建人物小传" -m "主要改动：
- pipeline characters 新增可重复 --repair-character
- characters 阶段支持只重建指定人物
- 增加非目标人物事实文件不变的回归测试

验证结果：
- python -m pytest tests/cli/test_character_repair_contract.py tests/pipeline/test_characters_pipeline_biographies.py -v：通过
- pipeline characters help 检查通过"
```

## Task 8：更新审计与报告的人物小传质量信号

**Files:**
- Modify: `src/novel_material/audit/rules.py`
- Modify: `src/novel_material/reporting/models.py`
- Modify: `src/novel_material/reporting/builder.py`
- Modify: `src/novel_material/reporting/markdown.py`
- Modify: `tests/audit/test_rules.py`
- Modify: `tests/reporting/test_builder.py`
- Modify: `tests/reporting/test_markdown.py`

- [ ] **Step 1: 编写审计测试**

新增测试：

- `profile_level=full` 但 `biography_complete=false`：`character_profile_fallback` error。
- `characters/_index.yaml` 声明目标 5 人，实际完整小传 4 人：`character_biography_incomplete` error。
- 简档 `profile_level=brief` 不因缺少完整小传字段报 error。

- [ ] **Step 2: 编写报告汇总测试**

断言报告包含：

- `biography_target_count`
- `biography_completed_count`
- `brief_profile_count`
- `biography_failed_count`

- [ ] **Step 3: 运行测试并确认失败**

Run:

```bash
python -m pytest tests/audit/test_rules.py tests/reporting/test_builder.py tests/reporting/test_markdown.py -v
```

Expected: FAIL，当前报告没有完整小传统计。

- [ ] **Step 4: 实现审计规则**

规则：

- 若 profile `role in {protagonist, antagonist}` 或 `profile_level=="full"`，仍要求 `arc_summary/psychology/relationships`。
- 若 `_index.yaml.biography_targets` 存在，所有目标必须有 `profile_level=full` 且 `biography_complete=true`。
- 简档只要求 `name/role/description/first_appearance_chapter/narrative_function` 中至少有可用信息，不要求心理和弧线。

- [ ] **Step 5: 实现报告汇总字段**

报告模型新增 `character_quality` 或扩展 `ArtifactQualityReport`，必须从审计 payload 或 `characters/_index.yaml` 的 report event 中获得；不得读取原文。

- [ ] **Step 6: 运行测试**

Run:

```bash
python -m pytest tests/audit/test_rules.py tests/reporting/test_builder.py tests/reporting/test_markdown.py tests/terminal/test_terminal_core.py -v
```

Expected: 全部通过。

- [ ] **Step 7: 提交**

```bash
git add src/novel_material/audit/rules.py src/novel_material/reporting/models.py src/novel_material/reporting/builder.py src/novel_material/reporting/markdown.py tests/audit/test_rules.py tests/reporting/test_builder.py tests/reporting/test_markdown.py tests/terminal/test_terminal_core.py
git commit -m "feat(audit): 增加人物小传质量信号" -m "主要改动：
- 审计识别完整小传目标缺失和伪完成
- 报告展示完整小传、简档和失败数量
- 保持简档与主要人物完整小传的不同质量要求

验证结果：
- python -m pytest tests/audit/test_rules.py tests/reporting/test_builder.py tests/reporting/test_markdown.py tests/terminal/test_terminal_core.py -v：通过"
```

## Task 9：更新 continue/status 与阶段契约

**Files:**
- Modify: `src/novel_material/pipeline/progress.py`
- Modify: `src/novel_material/pipeline/state.py`
- Modify: `tests/pipeline/test_state.py`
- Modify: `tests/pipeline/test_orchestrator.py`
- Modify: `tests/cli/test_pipeline_contract.py`

- [ ] **Step 1: 编写 v3 evaluation 完成状态测试**

断言：

- v3 `evaluation.yaml` 存在且可解析时，`evaluation` 阶段 complete。
- v2 旧文件存在时，兼容读取为 complete。
- 缺失 evaluation 但 `fast` 或 `--skip-navigation` 时不阻塞 continue。
- 缺失 evaluation 且 standard/deep 默认导航时，continue 从 evaluation 开始。

- [ ] **Step 2: 运行测试并确认失败**

Run:

```bash
python -m pytest tests/pipeline/test_state.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py -v
```

Expected: FAIL，当前状态逻辑仍按旧 evaluation/window 语义。

- [ ] **Step 3: 修改状态检查**

- `inspect_pipeline_state()` 使用 `load_evaluation_navigation()` 判断 evaluation 可用。
- `get_next_pending_stage()` 接受 `include_navigation`。
- `pipeline_common.run_continue_pipeline()` 根据 `_use_navigation(options)` 传入阶段计划。

- [ ] **Step 4: 运行测试**

Run:

```bash
python -m pytest tests/pipeline/test_state.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_pipeline_common.py -v
```

Expected: 全部通过。

- [ ] **Step 5: 提交**

```bash
git add src/novel_material/pipeline/progress.py src/novel_material/pipeline/state.py tests/pipeline/test_state.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_pipeline_common.py
git commit -m "feat(pipeline): 更新导航阶段断点语义" -m "主要改动：
- status/continue 识别 evaluation 3.0.0 与旧版兼容格式
- continue 根据 navigation 开关决定是否恢复 evaluate
- 移除对 --window 的阶段存在性推断

验证结果：
- python -m pytest tests/pipeline/test_state.py tests/pipeline/test_orchestrator.py tests/cli/test_pipeline_contract.py tests/cli/test_pipeline_common.py -v：通过"
```

## Task 10：性能预算与真实 smoke 验收

**Files:**
- Create: `tests/pipeline/test_character_performance_budget.py`
- Modify: `tests/reporting/test_performance_baseline.py`
- Modify: `docs/superpowers/execution/2026-06-29-global-navigation-and-character-biographies/STATE.md`

- [ ] **Step 1: 编写 fake LLM 性能预算测试**

测试要求：

- 1084 章节、134 人物候选。
- fake LLM 对完整小传目标返回固定结构。
- 只对 5–12 名目标调用完整小传，不对 134 人全部生成完整小传。
- rules + selection + report 在本地 2 秒内完成；LLM 部分用 fake，不测真实网络。
- 报告 baseline type 固定标记为 `navigation_character_rules_only`，不宣称真实 10% 门禁。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/pipeline/test_character_performance_budget.py -v`

Expected: FAIL，性能预算测试尚未实现。

- [ ] **Step 3: 实现测试所需轻量 fixture**

使用 `tmp_path`，不得读取或写入真实 `data/novels/`。

- [ ] **Step 4: 运行第一阶段和第二阶段相关测试**

Run:

```bash
python -m pytest tests/pipeline/test_character_performance_budget.py tests/reporting/test_performance_baseline.py -v
python -m pytest tests/audit tests/reporting tests/runtime tests/run_logging tests/pipeline tests/terminal tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v
```

Expected: 全部通过。

- [ ] **Step 5: 真实素材只读 smoke**

只读命令：

```bash
python -m novel_material.cli.main validate artifacts nm_novel_20260621_4si2
```

Expected:

- 不调用 LLM。
- 退出码仍为 3，直到真实素材被用户授权重跑 characters。
- 原事实文件哈希不变。

如果用户授权真实 LLM smoke，另行执行：

```bash
python -m novel_material.cli.main pipeline characters nm_novel_20260621_4si2 --repair-character 陈汉升
```

该命令会修改真实素材事实文件，必须单独确认，不属于默认验收。

- [ ] **Step 6: 提交**

```bash
git add tests/pipeline/test_character_performance_budget.py tests/reporting/test_performance_baseline.py
git commit -m "test(characters): 增加小传选择性能预算" -m "主要改动：
- 增加 1084 章节与 134 人物候选的本地性能预算测试
- 验证完整小传只覆盖自适应选择目标
- 明确本期不宣称真实 10% 发布门禁

验证结果：
- python -m pytest tests/pipeline/test_character_performance_budget.py tests/reporting/test_performance_baseline.py -v：通过
- 第二期开列 pytest 命令通过"
```

## Task 11：文档、CLI help 与完成门禁

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `docs/USER_MANUAL.md`
- Modify: `docs/REQUIREMENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/superpowers/execution/2026-06-29-global-navigation-and-character-biographies/STATE.md`

- [ ] **Step 1: 更新架构文档**

必须说明：

- evaluate 现在是前置导航，不等同于 `--window`。
- `evaluation.yaml` v3 字段和 v2 兼容读取。
- 人物完整小传与简档的区别。
- 定向修复命令。
- 第三期世界观/作品画像仍未实现。

- [ ] **Step 2: 更新用户手册**

命令示例：

```bash
nm pipeline full novel.txt --mode standard
nm pipeline full novel.txt --mode fast --navigation
nm pipeline full novel.txt --mode standard --skip-navigation
nm pipeline analyze nm_xxx --window
nm pipeline characters nm_xxx --repair-character 陈汉升
```

明确副作用：

- `pipeline characters --repair-character` 会修改目标人物 profile 和人物索引。
- `validate artifacts` 只读，不修复。

- [ ] **Step 3: 更新需求与 README**

不得声称检索质量提升；只能说人物素材结构更完整，供后续检索/写作 Agent 使用。

- [ ] **Step 4: 运行最终验证**

Run:

```bash
python -m pytest tests/audit tests/reporting tests/runtime tests/run_logging tests/pipeline tests/terminal tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v
python -m novel_material.cli.main pipeline full --help
python -m novel_material.cli.main pipeline analyze --help
python -m novel_material.cli.main pipeline characters --help
python -m novel_material.cli.main validate artifacts --help
python -m compileall -q src/novel_material
python scripts/check_v3_docs.py
git diff --check -- . ':(exclude)docs/feedback.md'
git status --short
```

Expected:

- pytest 全部通过，0 failed。
- help 显示 navigation、skip-navigation、repair-character、review。
- compileall、文档检查和 diff check 通过。
- `git status --short` 只包含计划内修改和用户原有 `docs/feedback.md`。

- [ ] **Step 5: 更新 STATE 为 complete 并提交**

```bash
git add ARCHITECTURE.md docs/USER_MANUAL.md docs/REQUIREMENTS.md docs/README.md docs/superpowers/execution/2026-06-29-global-navigation-and-character-biographies/STATE.md
git commit -m "docs(characters): 完成前置导航与人物小传文档" -m "主要改动：
- 更新前置导航、滑动窗口解耦和人物小传文档
- 记录第二期完成门禁与验证结果
- 明确第三期世界观和作品画像仍未实现

验证结果：
- 第二期开列 pytest 命令通过
- CLI help、compileall、文档检查和 Git 差异检查通过"
```

## 第二期完成门禁

- 新写入 `evaluation.yaml` 使用 `schema_version: 3.0.0`。
- 旧 `2.0.1` evaluation 能被读取端适配，且读取时不改写文件。
- `--window` 不再隐式触发 evaluate，也不因缺失 evaluation 直接失败。
- `standard/deep full` 默认运行前置导航；`fast` 默认跳过但可 `--navigation` 启用。
- 合格候选不少于 5 名时，完整小传覆盖 5–12 名；不足 5 名时覆盖全部合格候选并记录原因。
- 主要人物完整小传包含身份、目标、需求、恐惧、缺陷、关系变化、弧线阶段、关键场景、塑造方法、置信度和事实/推断标记。
- 主要人物兜底或伪完成继续被审计为 error；简档不因缺少完整小传字段误报。
- `nm pipeline characters <id> --repair-character <name>` 可重复传入，且只重建指定人物及受影响索引。
- 报告展示完整小传通过数量、简档数量和失败原因。
- 默认测试无网络、无数据库、无数据迁移副作用。
- 真实素材默认只读验收不修改事实文件；真实 LLM 修复必须另行授权。
- 未完成人工检索基线前，不声称检索质量提升。

## 交接给执行会话

执行入口：`docs/superpowers/execution/2026-06-29-global-navigation-and-character-biographies/STATE.md`。

每次新会话只需读取：

1. `AGENTS.md`
2. `STATE.md`
3. `STATE.md` 指向的当前 packet
4. `git status --short`
5. `git log -3 --oneline`

不要重新读取完整对话；除非当前 packet 明确要求，也不要读取本计划全文。
