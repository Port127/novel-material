# 题材感知分析 Profile 实施计划

> **给后续 agent/工程师的强制说明：** 执行本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`。所有步骤使用 checkbox（`- [ ]`）记录进度；如果上下文被压缩或中断，直接从第一个未勾选步骤继续。

**目标：** 在不破坏现有 `chapters.yaml` 和主流水线的前提下，新增一层“题材感知深度分析”，让不同题材使用不同分析字段、提示词和质量校验。

**架构：** 保留现有章级分析作为 L1 稳定层；新增 `chapter_insights/` 作为 L2/L3 深度分析层。新层由可组合 profile 驱动：`common + 题材 profile + 可选叙事模式 profile`。第一期按 GLM 5.0、Qwen 3.6 Plus 这类“中等推理、长上下文但不保证稳定深度分析”的模型能力设计，只实现 `common`、`xuanhuan`、`xianxia`、`suspense`，用小字段、强证据、可修复输出来验证机制。

**技术栈：** Python 3.10+、Typer CLI、YAML、Pydantic/自定义校验、现有 `novel_material.infra.llm`、现有 `novel_material.tags` 题材与标签系统。

**模型基准：** 不假设分析模型有强文学批评能力。Prompt、字段数量、校验和重试策略都以 GLM 5.0、Qwen 3.6 Plus 能稳定完成的“小步 JSON 抽取 + 轻量解释”为上限。

**运行目标：** 默认无人值守模式必须以 `standard` 为准，目标总耗时控制在 5-8 小时级别；`deep` 深度分析不能阻塞主流程完成；`fast` 模式用于先完成可检索入库。

---

## 0. 恢复协议

后续任意会话继续执行时，按这个顺序做：

1. 打开本文件。
2. 找到第一个未勾选的 `- [ ]`。
3. 只执行当前任务，不跨阶段乱改。
4. 每完成一个任务，运行该任务写明的验证命令。
5. 验证通过后，把对应 checkbox 勾上。
6. 如果完整测试套件失败，先确认是否是已知的 `word_count` 旧失败。
7. 在 Phase 1-6 完成前，不要把新字段合并进 `chapters.yaml`。
8. 如果模型输出质量不稳，先减少必填字段和证据长度，不要通过加长 prompt 解决。
9. 如果新增深度分析让整本书耗时增加超过 30%，优先改批量大小、字段数量和关键章节策略，不要接受一章一调用的实现。

## 1. 现有项目可复用资产

这些模块已经存在，执行时应复用，不要重写：

- `src/novel_material/material/classify.py`
  - `extract_sample_chapters()`：开头/中段/后段采样。
  - `parse_classification_result()`：解析 `genre_primary`、`genre_secondary`、`elements`、`style`、`quality`、`confidence`。
  - 当前限制：主要服务批量素材分类，还没有作为 pipeline 中 profile 路由的统一入口。
- `src/novel_material/material/classify_prompt.py`
  - 从数据库题材列表动态构造分类 prompt。
  - 当前限制：分类粒度偏 genre/style/quality，还没有 narrative_mode。
- `src/novel_material/pipeline/evaluate.py`
  - 生成 `evaluation.yaml`：`novel_type`、`main_thread_summary`、`core_characters_hint`、`stage_summaries`。
  - 可作为 profile 选择和深度分析上下文。
- `src/novel_material/pipeline/analyze.py`
  - 生成 `chapters.yaml` 和 `chapters/{0001}.yaml`。
  - 已有断点续传、范围分析、滑动窗口、质量重试、章节向量化。
  - 当前限制：章级 prompt 是通用的，没有题材差异。
- `src/novel_material/pipeline/tags.py`
  - 根据题材加载标签字典并生成 `tags.yaml`。
- `src/novel_material/tags/load.py`
  - `load_tags_for_genre(genre_primary, genre_secondary)` 已能按题材加载 `common + domain` 标签。
  - `infer_primary_from_secondary()` 已有二级题材到一级题材映射。
- `src/novel_material/storage/init_data.py`
  - 初始化 `genre_domain_map`，可作为第一版 profile 路由依据。
- `src/novel_material/storage/init_tags.py`
  - 已有 `element`、`setting`、`style`、`structure`、`chapter_function`、`character_archetype` 等标签维度。
- `src/novel_material/validation/quality.py`
  - 已有基础质量检查：schema、摘要长度、覆盖率、相似度。
  - 当前限制：只检查“格式像不像”，不检查“分析准不准、有无创作价值”。

## 2. 目标输出契约

新增输出路径：

```text
data/novels/{material_id}/chapter_insights/{chapter:04d}.yaml
```

单章最小结构：

```yaml
schema_version: "1.0"
material_id: "nm_novel_20260101_abcd"
chapter: 1
title: "第1章 开篇"
profiles: ["common", "xuanhuan"]
common:
  core_event: "主角被逐出家族并发现旧戒指异常。"
  conflict: "家族羞辱与主角隐藏机缘之间的冲突。"
  reader_hook: "戒指中的未知传承能否改变主角命运。"
  writing_takeaway: "先压低主角处境，再给出可验证但未完全揭示的机缘。"
genre:
  power_progression: "尚未突破，但建立修炼受阻背景。"
  resource_gain: "获得戒指传承线索。"
optional:
  scene_goal: "主角想保住最后的尊严并弄清戒指来源。"
  face_slapping: "铺垫后续对家族的反击。"
evidence:
  - field: "resource_gain"
    source: "chapter_summary"
    text: "主角被逐出家族，戒指出现异常。"
confidence: 0.8
quality:
  repaired: false
  validation_errors: []
```

## 2.1 模型能力约束

本计划必须按“模型不够强”来设计。GLM 5.0、Qwen 3.6 Plus 可以承担结构化抽取、局部归纳和短解释，但不要期待它们稳定完成长篇文学批评、复杂伏笔追踪或跨百章因果推理。

首版实现遵守这些规则：

- 单次调用只分析一章，不做多章全局综合判断。
- 上一条只适用于“逻辑分析粒度”，不代表 API 调用必须一章一次；实现上必须支持多章批量调用。
- 每个 profile 的必填字段保持少量：通用字段 4 个以内，题材字段 2-3 个以内。
- 模型只能基于 `chapters.yaml` 的章级分析、章节摘要和已有字段生成 insight；第一版不要求重新读取整章原文。
- 每个题材字段都要有 `evidence`，没有证据就写“无明显推进”或省略 optional 字段。
- optional 字段可以缺失，校验器不能因为 optional 缺失判失败。
- Prompt 只要求“事实 + 叙事功能 + 可复用写法”，不要要求复杂批评术语。
- 对无效 JSON 或缺字段结果最多修复 1 次；修复后仍失败也要落盘，但把 `quality.validation_errors` 写入文件。
- `confidence` 不能只相信模型自报；后续可以由校验结果下调。第一版规则：有校验错误则最高 0.4，无 evidence 则最高 0.3。
- 不使用 LLM judge 做自动质量评估；先用确定性评估集和人工抽检。

## 2.2 运行模式与时间预算

基于现有日志，完整 finalized 样本的耗时约 6.9-10.3 小时，其中章级分析占 5.4-8.9 小时。新增 insights 如果一章一调用，会额外增加 13-21 小时，这是不可接受的。因此本计划必须把时间预算作为功能契约。

三档运行模式：

```text
fast:
  目标：2.5-4.5 小时
  行为：完成入库、章级分析、基础标签、章节向量；跳过大纲 beats 深化、深度人物、deep insights。
  用途：先让素材进入可检索状态。

standard:
  目标：5-8 小时
  行为：完整主流水线 + 批量 core insights；deep insights 不阻塞 finalized。
  用途：默认无人值守模式。

deep:
  目标：9-15 小时
  行为：完整主流水线 + 全章节 core insights + 关键章节 deep insights。
  用途：质量优先、可过夜执行。
```

第一版默认采用：

```yaml
PIPELINE_RUN_MODE: standard
LLM_INSIGHT_BATCH_SIZE: 20
INSIGHTS_DEFAULT_DEPTH: core
INSIGHTS_KEY_CHAPTER_RATE: 0.2
PIPELINE_INCLUDE_INSIGHTS: true
PIPELINE_DEEP_INSIGHTS_BLOCKING: false
```

关键规则：

- `standard` 模式下，`chapter_insights/` 必须批量生成，不能一章一调用。
- `standard` 模式下，每批 insight 输入只使用 `chapters.yaml` 的结构化字段，不重新读取 `source.txt` 原文。
- `standard` 模式下，单批失败只能记录失败文件并继续；不能让整本书中断。
- `deep` 模式只分析关键章节：开头 3 章、结尾 3 章、`key_plot_point` 命中章节、高张力章节、强 hook 章节、每个序列的首尾章节。
- `full` 和 `continue` 默认只等待 `core insights`；`deep insights` 作为可续跑后处理。

## 3. 目标文件结构

新增：

```text
src/novel_material/analysis_profiles/__init__.py
src/novel_material/analysis_profiles/loader.py
src/novel_material/analysis_profiles/profiles/common.yaml
src/novel_material/analysis_profiles/profiles/xuanhuan.yaml
src/novel_material/analysis_profiles/profiles/xianxia.yaml
src/novel_material/analysis_profiles/profiles/suspense.yaml
src/novel_material/pipeline/profile_resolver.py
src/novel_material/pipeline/runtime_modes.py
src/novel_material/pipeline/insights_prompt.py
src/novel_material/pipeline/insights.py
src/novel_material/validation/insights.py
tests/analysis_profiles/test_loader.py
tests/pipeline/test_profile_resolver.py
tests/pipeline/test_runtime_modes.py
tests/pipeline/test_insights_prompt.py
tests/pipeline/test_insights_pipeline.py
tests/validation/test_insights.py
docs/GENRE_AWARE_ANALYSIS.md
```

修改：

```text
config/settings.yaml
src/novel_material/infra/config_service.py
src/novel_material/cli/pipeline.py
src/novel_material/cli/validate.py
src/novel_material/pipeline/progress.py
docs/USER_MANUAL.md
ARCHITECTURE.md
```

## Phase 0：确认当前测试基线

### Task 0.1：记录现有测试状态

**文件：**
- 读取：`tests/pipeline/test_ingest.py`
- 读取：`src/novel_material/pipeline/ingest.py`
- 修改：无

- [ ] **Step 1：运行当前完整测试**

```bash
python -m pytest
```

当前预期：

```text
1 failed, 49 passed, 1 skipped
```

已知失败：

```text
tests/pipeline/test_ingest.py::TestChapterSplit::test_word_count
```

- [ ] **Step 2：决定是否先修旧失败**

如果执行者要求完整测试必须全绿，则先修 `word_count` 口径。否则后续只运行新增测试，并在最终说明中标注“完整测试仍有旧的 word_count 失败”。

## Phase 1：Profile 契约与加载器

### Task 1.1：创建 Profile YAML

**文件：**
- 创建：`src/novel_material/analysis_profiles/__init__.py`
- 创建：`src/novel_material/analysis_profiles/profiles/common.yaml`
- 创建：`src/novel_material/analysis_profiles/profiles/xuanhuan.yaml`
- 创建：`src/novel_material/analysis_profiles/profiles/xianxia.yaml`
- 创建：`src/novel_material/analysis_profiles/profiles/suspense.yaml`

- [ ] **Step 1：创建 package 入口**

`src/novel_material/analysis_profiles/__init__.py`：

```python
"""Genre-aware analysis profile loading."""

from novel_material.analysis_profiles.loader import (
    AnalysisProfile,
    ProfileField,
    load_profile,
    load_profiles,
    merge_profiles,
)

__all__ = [
    "AnalysisProfile",
    "ProfileField",
    "load_profile",
    "load_profiles",
    "merge_profiles",
]
```

- [ ] **Step 2：创建通用 profile**

`src/novel_material/analysis_profiles/profiles/common.yaml`：

```yaml
name: common
display_name: 通用小说分析
applies_to: ["*"]
required_fields:
  core_event:
    description: 本章发生的核心事件
    min_length: 10
    max_length: 120
  conflict:
    description: 本章核心冲突
    min_length: 10
    max_length: 160
  reader_hook:
    description: 本章制造或延续的读者期待
    min_length: 8
    max_length: 160
  writing_takeaway:
    description: 可复用写法
    min_length: 12
    max_length: 220
optional_fields:
  scene_goal:
    description: 主要角色在本章的目标
  stakes:
    description: 失败代价或风险
  turning_point:
    description: 本章关键转折
  character_change:
    description: 人物心态、关系或处境变化
search_facets:
  - core_event
  - conflict
  - reader_hook
  - writing_takeaway
quality_rules:
  - field_presence
  - min_length
  - evidence_required
prompt_additions:
  - 先描述事实，再解释叙事功能，最后提炼可复用写法。
  - 不要使用空泛评价，例如“剧情精彩”“人物生动”；必须说明具体机制。
  - 如果章级信息不足，不要补写不存在的目标、转折或人物变化。
```

- [ ] **Step 3：创建玄幻 profile**

`src/novel_material/analysis_profiles/profiles/xuanhuan.yaml`：

```yaml
name: xuanhuan
display_name: 玄幻分析
applies_to: ["玄幻", "诸天无限"]
required_fields:
  power_progression:
    description: 修为、能力、血脉、功法或战力推进
    min_length: 8
    max_length: 160
  resource_gain:
    description: 资源、机缘、传承、法宝、信息收益
    min_length: 6
    max_length: 140
optional_fields:
  face_slapping:
    description: 打脸、压制、反击、身份反转的铺垫或兑现
    min_length: 6
    max_length: 160
  sect_faction_conflict:
    description: 宗门、家族、王朝、势力关系变化
  power_payoff:
    description: 前文能力或设定在本章的兑现
search_facets:
  - power_progression
  - resource_gain
  - face_slapping
  - sect_faction_conflict
quality_rules:
  - genre_field_presence
  - no_generic_power_words
prompt_additions:
  - 重点判断能力成长、资源收益、压制与反击链条。
  - 如果本章没有升级或资源收益，说明“无明显推进”，不要编造。
```

- [ ] **Step 4：创建仙侠 profile**

`src/novel_material/analysis_profiles/profiles/xianxia.yaml`：

```yaml
name: xianxia
display_name: 仙侠分析
applies_to: ["仙侠"]
required_fields:
  cultivation_rule:
    description: 修炼规则、境界限制、功法机制
    min_length: 8
    max_length: 180
  dao_heart_or_morality:
    description: 道心、因果、善恶、选择压力
    min_length: 8
    max_length: 160
optional_fields:
  sect_or_master_relation:
    description: 宗门、师徒、同门关系变化
    min_length: 6
    max_length: 160
  tribulation_or_breakthrough:
    description: 渡劫、破境、顿悟、瓶颈变化
search_facets:
  - cultivation_rule
  - dao_heart_or_morality
  - sect_or_master_relation
quality_rules:
  - genre_field_presence
  - evidence_required
prompt_additions:
  - 重点分析修炼规则如何限制角色选择，以及道心/因果如何推动情节。
  - 区分“玄幻战力爽点”和“仙侠修行规则/道心选择”。
```

- [ ] **Step 5：创建悬疑 profile**

`src/novel_material/analysis_profiles/profiles/suspense.yaml`：

```yaml
name: suspense
display_name: 悬疑分析
applies_to: ["悬疑灵异", "悬疑侦探女频"]
required_fields:
  clue:
    description: 本章新增或强化的线索
    min_length: 8
    max_length: 180
  information_gap:
    description: 读者、主角、嫌疑人之间的信息差
    min_length: 8
    max_length: 180
  mystery_progress:
    description: 谜题推进程度
    min_length: 8
    max_length: 160
optional_fields:
  reveal_or_misdirection:
    description: 揭示、误导或红鲱鱼
    min_length: 8
    max_length: 180
  suspect_state:
    description: 嫌疑对象或危险对象的状态变化
search_facets:
  - clue
  - information_gap
  - reveal_or_misdirection
  - mystery_progress
quality_rules:
  - clue_must_have_evidence
  - reveal_changes_understanding
prompt_additions:
  - 重点分析线索、误导、信息差和谜题推进，不要把单纯恐怖氛围误判为有效线索。
  - 每个 clue 必须能从章节摘要或原文中找到依据。
```

### Task 1.2：实现 Profile Loader

**文件：**
- 创建：`src/novel_material/analysis_profiles/loader.py`
- 创建：`tests/analysis_profiles/test_loader.py`

- [ ] **Step 1：先写失败测试**

`tests/analysis_profiles/test_loader.py`：

```python
"""题材感知 profile 加载测试。"""

from novel_material.analysis_profiles import load_profile, load_profiles, merge_profiles


def test_load_common_profile():
    profile = load_profile("common")
    assert profile.name == "common"
    assert "core_event" in profile.required_fields
    assert "field_presence" in profile.quality_rules


def test_load_profiles_preserves_order():
    profiles = load_profiles(["common", "xuanhuan"])
    assert [p.name for p in profiles] == ["common", "xuanhuan"]


def test_merge_profiles_combines_fields_and_prompt_additions():
    merged = merge_profiles(load_profiles(["common", "xuanhuan"]))
    assert merged.name == "common+xuanhuan"
    assert "core_event" in merged.required_fields
    assert "power_progression" in merged.required_fields
    assert any("能力成长" in item for item in merged.prompt_additions)
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/analysis_profiles/test_loader.py -v
```

预期：`ImportError` 或 `ModuleNotFoundError`。

- [ ] **Step 3：实现 loader**

`src/novel_material/analysis_profiles/loader.py`：

```python
"""Load and merge genre-aware analysis profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from novel_material.infra.yaml_io import load_yaml

PROFILE_DIR = Path(__file__).parent / "profiles"


@dataclass(frozen=True)
class ProfileField:
    """A field required or supported by an analysis profile."""

    name: str
    description: str
    min_length: int | None = None
    max_length: int | None = None


@dataclass(frozen=True)
class AnalysisProfile:
    """A genre-aware analysis profile."""

    name: str
    display_name: str
    applies_to: list[str] = field(default_factory=list)
    required_fields: dict[str, ProfileField] = field(default_factory=dict)
    optional_fields: dict[str, ProfileField] = field(default_factory=dict)
    search_facets: list[str] = field(default_factory=list)
    quality_rules: list[str] = field(default_factory=list)
    prompt_additions: list[str] = field(default_factory=list)


def _parse_fields(raw: dict[str, Any] | None) -> dict[str, ProfileField]:
    fields: dict[str, ProfileField] = {}
    for name, data in (raw or {}).items():
        fields[name] = ProfileField(
            name=name,
            description=str(data.get("description", "")),
            min_length=data.get("min_length"),
            max_length=data.get("max_length"),
        )
    return fields


def load_profile(name: str) -> AnalysisProfile:
    """Load a single profile by file stem."""
    profile_path = PROFILE_DIR / f"{name}.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"analysis profile not found: {profile_path}")

    data = load_yaml(profile_path)
    return AnalysisProfile(
        name=str(data["name"]),
        display_name=str(data.get("display_name", data["name"])),
        applies_to=list(data.get("applies_to", [])),
        required_fields=_parse_fields(data.get("required_fields")),
        optional_fields=_parse_fields(data.get("optional_fields")),
        search_facets=list(data.get("search_facets", [])),
        quality_rules=list(data.get("quality_rules", [])),
        prompt_additions=list(data.get("prompt_additions", [])),
    )


def load_profiles(names: list[str]) -> list[AnalysisProfile]:
    """Load profiles in the requested order."""
    return [load_profile(name) for name in names]


def merge_profiles(profiles: list[AnalysisProfile]) -> AnalysisProfile:
    """Merge profiles left-to-right; later profiles add genre-specific fields."""
    if not profiles:
        raise ValueError("at least one profile is required")

    required_fields: dict[str, ProfileField] = {}
    optional_fields: dict[str, ProfileField] = {}
    search_facets: list[str] = []
    quality_rules: list[str] = []
    prompt_additions: list[str] = []

    for profile in profiles:
        required_fields.update(profile.required_fields)
        optional_fields.update(profile.optional_fields)
        for facet in profile.search_facets:
            if facet not in search_facets:
                search_facets.append(facet)
        for rule in profile.quality_rules:
            if rule not in quality_rules:
                quality_rules.append(rule)
        prompt_additions.extend(profile.prompt_additions)

    return AnalysisProfile(
        name="+".join(p.name for p in profiles),
        display_name=" + ".join(p.display_name for p in profiles),
        applies_to=[item for p in profiles for item in p.applies_to],
        required_fields=required_fields,
        optional_fields=optional_fields,
        search_facets=search_facets,
        quality_rules=quality_rules,
        prompt_additions=prompt_additions,
    )
```

- [ ] **Step 4：验证通过**

```bash
python -m pytest tests/analysis_profiles/test_loader.py -v
```

预期：

```text
3 passed
```

## Phase 2：Profile 路由

### Task 2.1：根据现有 meta/tags 选择 profile

**文件：**
- 创建：`src/novel_material/pipeline/profile_resolver.py`
- 创建：`tests/pipeline/test_profile_resolver.py`

- [ ] **Step 1：写失败测试**

`tests/pipeline/test_profile_resolver.py`：

```python
"""根据题材元数据选择 analysis profiles。"""

from novel_material.pipeline.profile_resolver import resolve_profile_names


def test_resolve_defaults_to_common():
    assert resolve_profile_names({}) == ["common"]


def test_resolve_xuanhuan_from_meta_genre():
    meta = {"genre": ["玄幻"]}
    assert resolve_profile_names(meta) == ["common", "xuanhuan"]


def test_resolve_xianxia_from_secondary_genre():
    meta = {"genre": ["玄幻", "修真文明"]}
    assert resolve_profile_names(meta) == ["common", "xuanhuan", "xianxia"]


def test_resolve_suspense_from_genre():
    meta = {"genre": ["悬疑灵异"]}
    assert resolve_profile_names(meta) == ["common", "suspense"]


def test_explicit_profile_override_is_normalized():
    meta = {"genre": ["玄幻"]}
    assert resolve_profile_names(meta, explicit_profiles=["common", "suspense"]) == ["common", "suspense"]
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/pipeline/test_profile_resolver.py -v
```

预期：`ImportError`。

- [ ] **Step 3：实现 resolver**

`src/novel_material/pipeline/profile_resolver.py`：

```python
"""Resolve analysis profiles from novel metadata."""

from __future__ import annotations

from novel_material.tags.load import infer_primary_from_secondary

PRIMARY_TO_PROFILE = {
    "玄幻": "xuanhuan",
    "诸天无限": "xuanhuan",
    "仙侠": "xianxia",
    "悬疑灵异": "suspense",
    "悬疑侦探女频": "suspense",
}


def _normalize_profiles(names: list[str]) -> list[str]:
    result: list[str] = []
    for name in names:
        if name and name not in result:
            result.append(name)
    if "common" not in result:
        result.insert(0, "common")
    return result


def resolve_profile_names(meta: dict, explicit_profiles: list[str] | None = None) -> list[str]:
    """Resolve ordered profile names from meta.yaml-like data."""
    if explicit_profiles:
        return _normalize_profiles(explicit_profiles)

    profiles = ["common"]
    genres = meta.get("genre") or meta.get("genre_primary") or []
    if isinstance(genres, str):
        genres = [genres]

    for genre in genres:
        profile = PRIMARY_TO_PROFILE.get(genre)
        if profile:
            profiles.append(profile)

        inferred = infer_primary_from_secondary(genre)
        inferred_profile = PRIMARY_TO_PROFILE.get(inferred)
        if inferred_profile:
            profiles.append(inferred_profile)

    return _normalize_profiles(profiles)
```

- [ ] **Step 4：验证通过**

```bash
python -m pytest tests/pipeline/test_profile_resolver.py -v
```

预期：

```text
5 passed
```

## Phase 2.5：运行模式与时间预算配置

### Task 2.5.1：新增运行模式配置

**文件：**
- 创建：`src/novel_material/pipeline/runtime_modes.py`
- 创建：`tests/pipeline/test_runtime_modes.py`
- 修改：`config/settings.yaml`
- 修改：`src/novel_material/infra/config_service.py`

- [ ] **Step 1：写失败测试**

`tests/pipeline/test_runtime_modes.py`：

```python
"""运行模式配置测试。"""

from novel_material.pipeline.runtime_modes import RuntimeMode, get_runtime_mode


def test_standard_mode_defaults_are_time_bounded():
    mode = get_runtime_mode("standard")
    assert mode.name == "standard"
    assert mode.include_core_insights is True
    assert mode.block_on_deep_insights is False
    assert mode.insight_batch_size >= 10
    assert mode.insight_depth == "core"


def test_fast_mode_skips_blocking_insights():
    mode = get_runtime_mode("fast")
    assert mode.include_core_insights is False
    assert mode.block_on_deep_insights is False


def test_deep_mode_enables_key_chapter_deep_insights():
    mode = get_runtime_mode("deep")
    assert mode.include_core_insights is True
    assert mode.include_deep_insights is True
    assert mode.key_chapter_rate > 0
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/pipeline/test_runtime_modes.py -v
```

预期：`ImportError`。

- [ ] **Step 3：实现运行模式模块**

`src/novel_material/pipeline/runtime_modes.py`：

```python
"""Runtime modes for unattended pipeline execution."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeMode:
    """Pipeline runtime mode with explicit time/quality trade-offs."""

    name: str
    include_core_insights: bool
    include_deep_insights: bool
    block_on_deep_insights: bool
    insight_depth: str
    insight_batch_size: int
    key_chapter_rate: float


_MODES = {
    "fast": RuntimeMode(
        name="fast",
        include_core_insights=False,
        include_deep_insights=False,
        block_on_deep_insights=False,
        insight_depth="none",
        insight_batch_size=0,
        key_chapter_rate=0.0,
    ),
    "standard": RuntimeMode(
        name="standard",
        include_core_insights=True,
        include_deep_insights=False,
        block_on_deep_insights=False,
        insight_depth="core",
        insight_batch_size=20,
        key_chapter_rate=0.0,
    ),
    "deep": RuntimeMode(
        name="deep",
        include_core_insights=True,
        include_deep_insights=True,
        block_on_deep_insights=True,
        insight_depth="deep",
        insight_batch_size=10,
        key_chapter_rate=0.2,
    ),
}


def get_runtime_mode(name: str | None) -> RuntimeMode:
    """Return a runtime mode by name, defaulting to standard."""
    mode_name = name or "standard"
    if mode_name not in _MODES:
        allowed = ", ".join(sorted(_MODES))
        raise ValueError(f"未知运行模式: {mode_name}，可选: {allowed}")
    return _MODES[mode_name]
```

- [ ] **Step 4：追加 settings 默认值**

`config/settings.yaml` 增加：

```yaml
# ──────────────────────────────────────────────
# Pipeline 运行模式与 insights 时间预算
# ──────────────────────────────────────────────

PIPELINE_RUN_MODE: standard
LLM_INSIGHT_BATCH_SIZE: 20
INSIGHTS_DEFAULT_DEPTH: core
INSIGHTS_KEY_CHAPTER_RATE: 0.2
PIPELINE_INCLUDE_INSIGHTS: true
PIPELINE_DEEP_INSIGHTS_BLOCKING: false
```

- [ ] **Step 5：让 LLM 配置暴露 insight_batch_size**

`src/novel_material/infra/config_service.py` 的 `_build_llm_config()` 中，在 `chapter_batch_size` 附近加入：

```python
"insight_batch_size": int(settings.get("LLM_INSIGHT_BATCH_SIZE", 20)),
```

- [ ] **Step 6：验证通过**

```bash
python -m pytest tests/pipeline/test_runtime_modes.py -v
```

预期：

```text
3 passed
```

## Phase 3：深度分析 Prompt 构造

### Task 3.1：实现 profile-aware prompt builder

**文件：**
- 创建：`src/novel_material/pipeline/insights_prompt.py`
- 创建：`tests/pipeline/test_insights_prompt.py`

- [ ] **Step 1：写失败测试**

`tests/pipeline/test_insights_prompt.py`：

```python
"""深度分析 prompt 构造测试。"""

from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.pipeline.insights_prompt import (
    build_insight_schema_text,
    build_insight_system_prompt,
    build_repair_prompt,
)


def test_schema_includes_common_and_genre_fields():
    profile = merge_profiles(load_profiles(["common", "xuanhuan"]))
    schema = build_insight_schema_text(profile)
    assert '"core_event"' in schema
    assert '"power_progression"' in schema


def test_system_prompt_includes_profile_guidance():
    profile = merge_profiles(load_profiles(["common", "suspense"]))
    prompt = build_insight_system_prompt(profile)
    assert "线索" in prompt
    assert "可复用写法" in prompt
    assert "只输出 JSON" in prompt
    assert "不要编造" in prompt


def test_repair_prompt_includes_validation_errors():
    prompt = build_repair_prompt(["缺少必填字段: core_event"], {"common": {}})
    assert "缺少必填字段: core_event" in prompt
    assert "只修复这些错误" in prompt
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/pipeline/test_insights_prompt.py -v
```

预期：`ImportError`。

- [ ] **Step 3：实现 prompt builder**

`src/novel_material/pipeline/insights_prompt.py`：

```python
"""Prompt construction for chapter insight analysis."""

from __future__ import annotations

import json

from novel_material.analysis_profiles import AnalysisProfile

COMMON_FIELD_NAMES = {
    "core_event",
    "scene_goal",
    "conflict",
    "stakes",
    "turning_point",
    "reader_hook",
    "character_change",
    "writing_takeaway",
}


def build_insight_schema_text(profile: AnalysisProfile) -> str:
    """Build a JSON schema example from merged profile fields."""
    common_fields = {
        name: f"{field.description}，{field.min_length or 1}-{field.max_length or 200}字"
        for name, field in profile.required_fields.items()
        if name in COMMON_FIELD_NAMES
    }
    genre_fields = {
        name: f"{field.description}，{field.min_length or 1}-{field.max_length or 200}字"
        for name, field in profile.required_fields.items()
        if name not in COMMON_FIELD_NAMES
    }
    optional_fields = {
        name: field.description
        for name, field in profile.optional_fields.items()
    }
    example = {
        "schema_version": "1.0",
        "common": common_fields,
        "genre": genre_fields,
        "optional": optional_fields,
        "evidence": [{"field": "core_event", "source": "chapter_summary", "text": "依据文本"}],
        "confidence": 0.8,
        "quality": {"repaired": False, "validation_errors": []},
    }
    return json.dumps(example, ensure_ascii=False, indent=2)


def build_insight_system_prompt(profile: AnalysisProfile) -> str:
    """Build the system prompt for chapter insight analysis."""
    additions = "\n".join(f"- {item}" for item in profile.prompt_additions)
    return f"""你是专业的小说创作机制分析师，但必须按中等模型可稳定完成的方式工作。

你的任务不是复述剧情，而是分析这一章为什么有效、如何服务读者期待、如何为创作提供可复用经验。

当前分析 profile: {profile.display_name}

分析要求：
- 只输出 JSON，不要输出 Markdown、解释文字或推理过程。
- 事实必须来自章节摘要、章级分析字段或原文片段。
- 先给具体事件，再解释叙事功能。
- writing_takeaway 必须是可执行的写作建议。
- 每个必填字段尽量对应 1 条 evidence；evidence.text 控制在 120 字以内。
- 如果信息不足，不要编造；必填字段写“无明显推进”，optional 字段可以省略。
- confidence 表示本次分析可信度，范围 0.0-1.0。
- 不要使用“剧情精彩”“人物饱满”“节奏紧凑”这类泛化评价。

profile 额外要求：
{additions}
"""


def build_repair_prompt(errors: list[str], previous_result: dict) -> str:
    """Build a constrained repair prompt for invalid insight JSON."""
    return f"""上一次 JSON 没有通过校验。

只修复这些错误，不要增加无依据内容：
{json.dumps(errors, ensure_ascii=False, indent=2)}

上一次结果：
{json.dumps(previous_result, ensure_ascii=False, indent=2)}

请只输出修复后的 JSON。
"""
```

- [ ] **Step 4：验证通过**

```bash
python -m pytest tests/pipeline/test_insights_prompt.py -v
```

预期：

```text
3 passed
```

## Phase 4：Insight 校验

### Task 4.1：实现单章 insight 校验

**文件：**
- 创建：`src/novel_material/validation/insights.py`
- 创建：`tests/validation/test_insights.py`

- [ ] **Step 1：写失败测试**

`tests/validation/test_insights.py`：

```python
"""chapter_insights 校验测试。"""

from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.validation.insights import validate_insight


def test_valid_insight_passes():
    profile = merge_profiles(load_profiles(["common", "xuanhuan"]))
    insight = {
        "schema_version": "1.0",
        "common": {
            "core_event": "主角被家族羞辱并发现戒指异常。",
            "scene_goal": "主角想保住尊严并弄清戒指来历。",
            "conflict": "家族压迫与隐藏机缘之间形成冲突。",
            "stakes": "失败会失去修炼资源和身份。",
            "turning_point": "戒指回应血液，暗示传承。",
            "reader_hook": "戒指传承是否能改变命运。",
            "character_change": "主角从被动受辱转向主动寻找机会。",
            "writing_takeaway": "先压低处境，再给出可验证但未揭开的机缘。",
        },
        "genre": {
            "power_progression": "没有突破，但建立修炼受阻背景。",
            "resource_gain": "获得戒指传承线索。",
            "face_slapping": "铺垫后续对家族的反击。",
        },
        "evidence": [
            {"field": "core_event", "source": "chapter_summary", "text": "主角被逐出家族，戒指出现异常。"},
            {"field": "resource_gain", "source": "chapter_summary", "text": "戒指出现异常，提示传承线索。"},
        ],
        "confidence": 0.8,
    }
    assert validate_insight(insight, profile) == []


def test_missing_required_field_fails():
    profile = merge_profiles(load_profiles(["common"]))
    insight = {"schema_version": "1.0", "common": {}, "genre": {}, "evidence": [], "confidence": 0.8}
    errors = validate_insight(insight, profile)
    assert any("core_event" in error for error in errors)
    assert any("evidence" in error for error in errors)
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/validation/test_insights.py -v
```

预期：`ImportError`。

- [ ] **Step 3：实现校验器**

`src/novel_material/validation/insights.py`：

```python
"""Validation helpers for chapter insight YAML."""

from __future__ import annotations

from novel_material.analysis_profiles import AnalysisProfile

COMMON_FIELD_NAMES = {
    "core_event",
    "scene_goal",
    "conflict",
    "stakes",
    "turning_point",
    "reader_hook",
    "character_change",
    "writing_takeaway",
}


def validate_insight(insight: dict, profile: AnalysisProfile) -> list[str]:
    """Validate one chapter insight against a merged profile."""
    errors: list[str] = []

    if insight.get("schema_version") != "1.0":
        errors.append("schema_version 必须为 1.0")

    common = insight.get("common")
    if not isinstance(common, dict):
        errors.append("common 必须是对象")
        common = {}

    genre = insight.get("genre")
    if not isinstance(genre, dict):
        errors.append("genre 必须是对象")
        genre = {}

    for name, field in profile.required_fields.items():
        container = common if name in COMMON_FIELD_NAMES else genre
        value = container.get(name)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"缺少必填字段: {name}")
            continue
        if field.min_length is not None and len(value) < field.min_length:
            errors.append(f"{name} 过短: {len(value)} < {field.min_length}")
        if field.max_length is not None and len(value) > field.max_length:
            errors.append(f"{name} 过长: {len(value)} > {field.max_length}")

    evidence = insight.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence 至少需要 1 条")
    else:
        for index, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                errors.append(f"evidence[{index}] 必须是对象")
                continue
            for key in ("field", "source", "text"):
                value = item.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"evidence[{index}].{key} 不能为空")
            text = item.get("text")
            if isinstance(text, str) and len(text) > 120:
                errors.append(f"evidence[{index}].text 过长: {len(text)} > 120")

    confidence = insight.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append("confidence 必须是 0.0-1.0 的数字")

    return errors
```

- [ ] **Step 4：验证通过**

```bash
python -m pytest tests/validation/test_insights.py -v
```

预期：

```text
4 passed
```

## Phase 5：Insight 生成流水线

Phase 5 必须以批量处理为准。禁止实现“一章一次 LLM 调用”的全书默认流程；单章调用只允许作为批量缺失章节的降级补齐。

### Task 5.1：实现批量深度分析生成

**文件：**
- 创建：`src/novel_material/pipeline/insights.py`
- 创建：`tests/pipeline/test_insights_pipeline.py`

- [ ] **Step 1：先写不依赖 LLM 的测试**

`tests/pipeline/test_insights_pipeline.py`：

```python
"""chapter_insights 流水线辅助函数测试。"""

from pathlib import Path

from novel_material.pipeline.insights import (
    build_insight_batch_user_prompt,
    build_insight_user_prompt,
    get_insight_file,
    split_batches,
)


def test_get_insight_file_uses_zero_padded_chapter(tmp_path: Path):
    assert get_insight_file(tmp_path, 7) == tmp_path / "chapter_insights" / "0007.yaml"


def test_user_prompt_includes_chapter_summary_and_schema():
    ch = {
        "chapter": 1,
        "title": "第1章 开篇",
        "summary": "主角被逐出家族，发现戒指异常。",
        "key_event": "戒指出现异常",
    }
    prompt = build_insight_user_prompt(ch, "SCHEMA")
    assert "第1章 开篇" in prompt
    assert "主角被逐出家族" in prompt
    assert "SCHEMA" in prompt


def test_split_batches_respects_batch_size():
    chapters = [{"chapter": i} for i in range(1, 46)]
    batches = split_batches(chapters, 20)
    assert [len(batch) for batch in batches] == [20, 20, 5]


def test_batch_prompt_contains_multiple_chapters():
    chapters = [
        {"chapter": 1, "title": "第1章", "summary": "主角落难。"},
        {"chapter": 2, "title": "第2章", "summary": "主角获得线索。"},
    ]
    prompt = build_insight_batch_user_prompt(chapters, "SCHEMA")
    assert "第1章" in prompt
    assert "第2章" in prompt
    assert "JSON 数组" in prompt
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/pipeline/test_insights_pipeline.py -v
```

预期：`ImportError`。

- [ ] **Step 3：实现流水线骨架**

`src/novel_material/pipeline/insights.py`：

```python
"""Genre-aware chapter insight generation."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import call_llm, load_config
from novel_material.infra.progress import get_pipeline_logger
from novel_material.infra.yaml_io import load_yaml, load_yaml_list, save_yaml
from novel_material.pipeline.insights_prompt import (
    build_insight_schema_text,
    build_insight_system_prompt,
    build_repair_prompt,
)
from novel_material.pipeline.profile_resolver import resolve_profile_names
from novel_material.validation.insights import validate_insight

logger = get_pipeline_logger()


def get_insight_file(novel_dir: Path, chapter_num: int) -> Path:
    """Return the per-chapter insight file path."""
    return novel_dir / "chapter_insights" / f"{chapter_num:04d}.yaml"


def split_batches(chapters: list[dict], batch_size: int) -> list[list[dict]]:
    """Split chapters into stable batches."""
    size = max(1, batch_size)
    return [chapters[i:i + size] for i in range(0, len(chapters), size)]


def build_insight_user_prompt(chapter: dict, schema_text: str) -> str:
    """Build user prompt from existing chapter analysis."""
    return f"""请基于以下章级分析生成深度创作机制分析。

章节号：{chapter.get("chapter")}
标题：{chapter.get("title")}
摘要：{chapter.get("summary", "")}
关键事件：{chapter.get("key_event", "")}
章节功能：{chapter.get("chapter_functions", [])}
人物：{chapter.get("characters_appear", [])}
张力：{chapter.get("tension_level")}
节奏：{chapter.get("pacing")}
情绪：{chapter.get("emotional_tone", [])}
场景类型：{chapter.get("scene_type", [])}
钩子：{chapter.get("hook_type", "")}

请严格返回 JSON，格式如下：
{schema_text}
"""


def build_insight_batch_user_prompt(chapters: list[dict], schema_text: str) -> str:
    """Build a compact batch prompt from existing chapter analysis."""
    lines = []
    for chapter in chapters:
        lines.append(
            "\n".join([
                f"章节号：{chapter.get('chapter')}",
                f"标题：{chapter.get('title')}",
                f"摘要：{chapter.get('summary', '')}",
                f"关键事件：{chapter.get('key_event', '')}",
                f"章节功能：{chapter.get('chapter_functions', [])}",
                f"张力：{chapter.get('tension_level')}",
                f"钩子：{chapter.get('hook_type', '')}",
            ])
        )
    joined = "\n\n---\n\n".join(lines)
    return f"""请基于以下多章章级分析生成深度创作机制分析。

要求：
- 返回 JSON 数组，每个元素对应一章。
- 每个元素必须包含 chapter、common、genre、evidence、confidence。
- 不要输出 Markdown。

章节数据：
{joined}

单章 JSON 格式示例：
{schema_text}
"""


def _cap_confidence(insight: dict, errors: list[str]) -> None:
    """Cap confidence when deterministic validation found quality problems."""
    confidence = insight.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    confidence = max(0.0, min(float(confidence), 1.0))
    if errors:
        confidence = min(confidence, 0.4)
    if not insight.get("evidence"):
        confidence = min(confidence, 0.3)
    insight["confidence"] = confidence


def generate_chapter_insights(
    material_id: str,
    start_ch: int | None = None,
    end_ch: int | None = None,
    provider: str | None = None,
    explicit_profiles: list[str] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> bool:
    """Generate genre-aware insights for analyzed chapters."""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    meta = load_yaml(novel_dir / "meta.yaml") if (novel_dir / "meta.yaml").exists() else {}
    profile_names = resolve_profile_names(meta, explicit_profiles=explicit_profiles)
    profile = merge_profiles(load_profiles(profile_names))

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        logger.error(f"[{material_id}] chapters.yaml 不存在，请先运行 nm pipeline analyze")
        return False

    chapters = [
        ch for ch in load_yaml_list(chapters_file)
        if isinstance(ch, dict)
        and (start_ch is None or ch.get("chapter", 0) >= start_ch)
        and (end_ch is None or ch.get("chapter", 0) <= end_ch)
    ]
    total = len(chapters)
    if total == 0:
        logger.warning(f"[{material_id}] 没有可分析章节")
        return True

    insights_dir = novel_dir / "chapter_insights"
    insights_dir.mkdir(exist_ok=True)

    config = load_config(provider)
    system_prompt = build_insight_system_prompt(profile)
    schema_text = build_insight_schema_text(profile)

    pending = [
        chapter for chapter in chapters
        if not get_insight_file(novel_dir, int(chapter["chapter"])).exists()
    ]
    done = total - len(pending)
    if progress_callback:
        progress_callback(done, total, f"断点续传：已完成 {done} 章")

    batch_size = int(config["llm"].get("insight_batch_size", 20))
    for batch_idx, batch in enumerate(split_batches(pending, batch_size), start=1):
        try:
            result = call_llm(
                system_prompt=system_prompt,
                user_prompt=build_insight_batch_user_prompt(batch, schema_text),
                config=config,
                context=f"{material_id} insights_batch#{batch_idx}",
            )
        except Exception as exc:
            logger.warning(f"[{material_id}] insight 批次 {batch_idx} 失败，写入失败占位并继续: {exc}")
            result = []

        if isinstance(result, dict):
            raw_items = result.get("items", [])
        elif isinstance(result, list):
            raw_items = result
        else:
            raw_items = []

        by_chapter = {
            int(item.get("chapter")): item
            for item in raw_items
            if isinstance(item, dict) and str(item.get("chapter", "")).isdigit()
        }

        for chapter in batch:
            ch_num = int(chapter["chapter"])
            raw = by_chapter.get(ch_num, {})
            repaired = False
            insight = {
                **raw,
                "schema_version": "1.0",
                "material_id": material_id,
                "chapter": ch_num,
                "title": chapter.get("title", ""),
                "profiles": profile_names,
            }
            errors = validate_insight(insight, profile)

            if errors and raw:
                repaired = True
                repair_result = call_llm(
                    system_prompt="你是严格的 JSON 修复器，只修复格式和缺失字段，不增加无依据内容。",
                    user_prompt=build_repair_prompt(errors, raw),
                    config=config,
                    context=f"{material_id} insight#{ch_num} repair",
                )
                if not isinstance(repair_result, dict):
                    repair_result = {}
                insight = {
                    **repair_result,
                    "schema_version": "1.0",
                    "material_id": material_id,
                    "chapter": ch_num,
                    "title": chapter.get("title", ""),
                    "profiles": profile_names,
                }
                errors = validate_insight(insight, profile)

            if not raw:
                errors = [f"批次 {batch_idx} 未返回本章结果"]

            quality = insight.get("quality")
            if not isinstance(quality, dict):
                quality = {}
            insight["quality"] = quality
            insight["quality"]["repaired"] = repaired
            insight["quality"]["validation_errors"] = errors
            _cap_confidence(insight, errors)
            save_yaml(get_insight_file(novel_dir, ch_num), insight)

            done += 1
            if progress_callback:
                progress_callback(done, total, f"完成 insight 批次 {batch_idx}: 第 {ch_num} 章")

    return True
```

- [ ] **Step 4：验证通过**

```bash
python -m pytest tests/pipeline/test_insights_pipeline.py -v
```

预期：

```text
4 passed
```

### Task 5.2：新增 CLI：`nm pipeline insights`

**文件：**
- 修改：`src/novel_material/cli/pipeline.py`

- [ ] **Step 1：添加 import**

在 `src/novel_material/cli/pipeline.py` 顶部加入：

```python
from novel_material.pipeline.insights import generate_chapter_insights
```

- [ ] **Step 2：在 `cmd_analyze` 附近添加命令**

```python
@app.command("insights")
def cmd_insights(
    material_id: str = typer.Argument(..., help="素材 ID"),
    start: int = typer.Option(None, "--start", "-s", help="起始章节号"),
    end: int = typer.Option(None, "--end", "-e", help="结束章节号"),
    provider: str = typer.Option(None, "--provider", "-p", help="服务商名称"),
    profile: list[str] = typer.Option(None, "--profile", help="显式指定 profile，可重复传入"),
):
    """题材感知深度分析：生成 chapter_insights/{chapter}.yaml。"""
    novel_dir = NOVELS_DIR / material_id
    chapter_index = load_yaml_list(novel_dir / "chapter_index.yaml")
    total_chapters = len(chapter_index)

    if start is not None and start < 1:
        console.print("[red]起始章节号必须 >= 1[/red]")
        raise typer.Exit(1)
    if start is not None and end is not None and end < start:
        console.print("[red]结束章节号必须 >= 起始章节号[/red]")
        raise typer.Exit(1)
    if start is not None and start > total_chapters:
        console.print(f"[red]起始章节号 {start} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)
    if end is not None and end > total_chapters:
        console.print(f"[red]结束章节号 {end} 超出总章数 {total_chapters}[/red]")
        raise typer.Exit(1)

    chapters_in_range = [
        ch for ch in chapter_index
        if (start is None or ch["chapter"] >= start)
        and (end is None or ch["chapter"] <= end)
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress_bar:
        task = progress_bar.add_task(f"深度分析: {material_id}", total=len(chapters_in_range))

        def update_progress(done: int, total: int, desc: str):
            progress_bar.update(task, completed=done, description=f"深度分析: {desc}")

        with silent_console():
            success = generate_chapter_insights(
                material_id,
                start_ch=start,
                end_ch=end,
                provider=provider,
                explicit_profiles=profile,
                progress_callback=update_progress,
            )

    if not success:
        console.print("[red]深度分析失败[/red]")
        raise typer.Exit(1)
    console.print("[green]深度分析完成[/green]")
```

- [ ] **Step 3：编译检查**

```bash
python -m compileall -q src tests
```

预期：无输出，退出码为 0。

### Task 5.3：把 core insights 接入 `full` / `continue` / `status`

**文件：**
- 修改：`src/novel_material/pipeline/progress.py`
- 修改：`src/novel_material/cli/pipeline.py`
- 测试：`tests/pipeline/test_insights_pipeline.py`

- [ ] **Step 1：新增进度判断测试**

追加到 `tests/pipeline/test_insights_pipeline.py`：

```python
from novel_material.pipeline.progress import has_complete_insights


def test_has_complete_insights_counts_yaml_files(tmp_path: Path):
    novel_dir = tmp_path
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 1\n  title: A\n- chapter: 2\n  title: B\n",
        encoding="utf-8",
    )
    insights_dir = novel_dir / "chapter_insights"
    insights_dir.mkdir()
    (insights_dir / "0001.yaml").write_text("chapter: 1\n", encoding="utf-8")
    assert has_complete_insights(novel_dir) is False

    (insights_dir / "0002.yaml").write_text("chapter: 2\n", encoding="utf-8")
    assert has_complete_insights(novel_dir) is True
```

- [ ] **Step 2：运行测试确认失败**

```bash
python -m pytest tests/pipeline/test_insights_pipeline.py::test_has_complete_insights_counts_yaml_files -v
```

预期：`ImportError`。

- [ ] **Step 3：在 progress 中加入 insights 状态**

`src/novel_material/pipeline/progress.py` 增加：

```python
def has_complete_insights(novel_dir: Path) -> bool:
    """Return True when chapter_insights has one YAML per indexed chapter."""
    chapter_index_file = novel_dir / "chapter_index.yaml"
    if not chapter_index_file.exists():
        return False
    chapter_index = load_yaml_list(chapter_index_file)
    total = len(chapter_index)
    if total == 0:
        return False
    insights_dir = novel_dir / "chapter_insights"
    if not insights_dir.exists():
        return False
    return len(list(insights_dir.glob("*.yaml"))) >= total
```

在 `PIPELINE_STAGES` 中把 insights 放在标签之后、精调之前：

```python
("深度分析", "insights", True),
```

修改 `get_pipeline_stages()`，让 `fast` 模式可以不计入 insights：

```python
def get_pipeline_stages(include_evaluation: bool = False, include_insights: bool = True) -> list:
    """获取流水线阶段列表（不含数据库同步）。"""
    return [
        (name, key)
        for name, key, counted in PIPELINE_STAGES
        if (counted or (key == "evaluation" and include_evaluation))
        and (include_insights or key != "insights")
    ]
```

修改 `get_next_pending_stage()` 签名：

```python
def get_next_pending_stage(progress: dict, include_insights: bool = True) -> str | None:
```

标签阶段之后的 insights 判断必须受 `include_insights` 控制：

```python
if include_insights and not progress.get("insights"):
    return "insights"
```

修改 `calculate_total_stages()` 签名：

```python
def calculate_total_stages(has_evaluation: bool, include_insights: bool = True) -> int:
    return len(get_pipeline_stages(has_evaluation, include_insights=include_insights))
```

在 `get_pipeline_progress()` 返回值中加入：

```python
"insights": has_complete_insights(novel_dir),
```

在 `get_next_pending_stage()` 中，标签之后加入：

```python
if not progress.get("insights"):
    return "insights"
```

- [ ] **Step 4：在 full 中接入 standard core insights**

`src/novel_material/cli/pipeline.py`：

```python
from novel_material.pipeline.insights import generate_chapter_insights
from novel_material.pipeline.runtime_modes import get_runtime_mode
```

给 `cmd_full()` 和 `cmd_continue()` 增加参数：

```python
mode: str = typer.Option("standard", "--mode", help="运行模式：fast / standard / deep"),
```

在 `cmd_full()` 标签阶段之后、精调阶段之前加入：

```python
runtime_mode = get_runtime_mode(mode)
total_stages = calculate_total_stages(use_window, include_insights=runtime_mode.include_core_insights)
if runtime_mode.include_core_insights:
    insights_stage = tags_stage + 1
    task_insights = progress.add_task(
        f"阶段 {insights_stage}/{total_stages}: 深度分析",
        total=total_chapters,
    )

    def update_insights_progress(done: int, total: int, desc: str):
        progress.update(
            task_insights,
            total=total,
            completed=done,
            description=f"阶段 {insights_stage}/{total_stages}: {desc}",
        )

    with silent_console():
        generate_chapter_insights(
            material_id,
            provider=provider,
            progress_callback=update_insights_progress,
        )
    progress.remove_task(task_insights)
```

注意：实现时要相应调整 `refine_stage` 的编号，不能让阶段编号重复。

- [ ] **Step 5：在 continue 中接入 insights**

`cmd_continue()` 中，在标签阶段之后、精调阶段之前加入：

```python
runtime_mode = get_runtime_mode(mode)
if runtime_mode.include_core_insights and not progress.get("insights"):
    console.print(f"[cyan]阶段 {current_stage}/{total_stages}: 深度分析...[/cyan]")
    task = progress_bar.add_task(f"阶段 {current_stage}/{total_stages}: 深度分析", total=total_chapters)

    def update_insights_progress(done: int, total: int, desc: str):
        progress_bar.update(task, total=total, completed=done, description=f"阶段 {current_stage}/{total_stages}: {desc}")

    with silent_console():
        generate_chapter_insights(
            material_id,
            provider=provider,
            progress_callback=update_insights_progress,
        )
    progress_bar.remove_task(task)
    current_stage += 1
```

- [ ] **Step 6：验证通过**

```bash
python -m pytest tests/pipeline/test_insights_pipeline.py -v
python -m compileall -q src tests
```

预期：测试通过；编译无输出。

## Phase 6：Insight 校验 CLI

### Task 6.1：新增 `nm validate insights`

**文件：**
- 修改：`src/novel_material/validation/insights.py`
- 修改：`src/novel_material/cli/validate.py`

- [ ] **Step 1：新增 material 级校验函数**

追加到 `src/novel_material/validation/insights.py`：

```python
from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml
from novel_material.pipeline.profile_resolver import resolve_profile_names


def validate_material_insights(material_id: str) -> list[str]:
    """Validate all generated chapter insight files for one material."""
    novel_dir = NOVELS_DIR / material_id
    meta = load_yaml(novel_dir / "meta.yaml") if (novel_dir / "meta.yaml").exists() else {}
    profile = merge_profiles(load_profiles(resolve_profile_names(meta)))
    insights_dir = novel_dir / "chapter_insights"
    if not insights_dir.exists():
        return [f"chapter_insights 不存在: {insights_dir}"]

    errors: list[str] = []
    for path in sorted(insights_dir.glob("*.yaml")):
        insight = load_yaml(path)
        for error in validate_insight(insight, profile):
            errors.append(f"{path.name}: {error}")
    return errors
```

- [ ] **Step 2：在 CLI 中引入函数**

`src/novel_material/cli/validate.py` 增加：

```python
from novel_material.validation.insights import validate_material_insights
```

- [ ] **Step 3：新增命令**

```python
@app.command("insights")
def cmd_validate_insights(
    material_id: str = typer.Argument(..., help="素材 ID"),
):
    """校验 chapter_insights 深度分析结果。"""
    errors = validate_material_insights(material_id)
    if errors:
        for error in errors:
            console.print(f"[red]✗[/red] {error}")
        raise typer.Exit(1)
    console.print(f"[green]素材 {material_id} 深度分析校验通过[/green]")
```

- [ ] **Step 4：编译检查**

```bash
python -m compileall -q src tests
```

预期：无输出，退出码为 0。

## Phase 7：先做 YAML 搜索，不急着改数据库

### Task 7.1：新增 `nm search insight`

**文件：**
- 创建：`src/novel_material/search/insight.py`
- 修改：`src/novel_material/cli/search.py`
- 创建：`tests/search/test_insight_search.py`

- [ ] **Step 1：实现 YAML 扫描搜索**

搜索范围：

```text
common.conflict
common.reader_hook
common.writing_takeaway
genre.*
```

返回结构：

```python
{
    "material_id": material_id,
    "chapter": chapter,
    "title": title,
    "profiles": profiles,
    "matched_fields": matched_fields,
    "writing_takeaway": writing_takeaway,
}
```

- [ ] **Step 2：添加 CLI**

命令：

```bash
nm search insight "主角被压制后反杀"
```

展示字段：

```text
章节 / 标题 / 命中字段 / writing_takeaway
```

- [ ] **Step 3：测试不依赖 PostgreSQL**

测试使用临时目录和 YAML 文件，不连接数据库。

## Phase 8：评估集

### Task 8.1：新增人工评估样本

**文件：**
- 创建：`eval/genre_profile_cases.yaml`
- 创建：`src/novel_material/eval/insights_eval.py`
- 创建：`tests/eval/test_insights_eval.py`

- [ ] **Step 1：创建评估数据格式**

`eval/genre_profile_cases.yaml`：

```yaml
cases:
  - id: xuanhuan_opening_001
    genre: 玄幻
    expected_profiles: ["common", "xuanhuan"]
    expected_fields:
      common:
        conflict_contains: ["羞辱", "压制"]
        reader_hook_contains: ["机缘", "戒指", "传承"]
      genre:
        resource_gain_contains: ["戒指", "传承"]
```

- [ ] **Step 2：先写确定性 scorer**

第一版只做关键词/字段命中，不使用 LLM judge。

指标：

```text
field_presence_rate
keyword_hit_rate
evidence_presence_rate
profile_resolution_accuracy
repair_rate
invalid_after_repair_rate
generic_phrase_rate
```

其中：

- `repair_rate`：触发二次修复的章节比例，比例过高说明 prompt 或字段设计过难。
- `invalid_after_repair_rate`：修复后仍有 `quality.validation_errors` 的比例，首版应低于 10%。
- `generic_phrase_rate`：出现“剧情精彩”“人物饱满”“节奏紧凑”等泛化评价的比例，首版应低于 5%。

## Phase 9：文档

### Task 9.1：补中文使用文档

**文件：**
- 创建：`docs/GENRE_AWARE_ANALYSIS.md`
- 修改：`docs/USER_MANUAL.md`
- 修改：`ARCHITECTURE.md`

- [ ] **Step 1：创建专题文档**

`docs/GENRE_AWARE_ANALYSIS.md` 至少包含：

```text
1. 为什么需要题材感知分析
2. profile 组合规则
3. 第一期支持：common / xuanhuan / xianxia / suspense
4. 输出路径：chapter_insights/{chapter}.yaml
5. CLI：
   nm pipeline insights <id> --start 1 --end 10
   nm validate insights <id>
6. 如何新增一个题材 profile
7. 质量评估清单
8. 模型能力边界：以 GLM 5.0、Qwen 3.6 Plus 为基准，字段少量、证据优先、最多一次修复
9. 运行模式：fast / standard / deep 的差异、默认值和预计耗时
```

- [ ] **Step 2：更新用户手册命令**

加入：

```bash
nm pipeline insights <id> [--start N] [--end N] [--profile NAME]
nm pipeline full <file> --mode standard
nm pipeline continue <id> --mode standard
nm validate insights <id>
```

- [ ] **Step 3：更新架构说明**

说明：

```text
chapter_insights/ 是新增深度分析层，不替代 chapters.yaml。
```

## Phase 10：端到端验证

### Task 10.1：运行聚焦测试矩阵

**文件：**
- 修改：无

- [ ] **Step 1：运行新增测试**

```bash
python -m pytest \
  tests/analysis_profiles/test_loader.py \
  tests/pipeline/test_profile_resolver.py \
  tests/pipeline/test_insights_prompt.py \
  tests/validation/test_insights.py \
  tests/pipeline/test_insights_pipeline.py \
  -v
```

预期：全部通过。

- [ ] **Step 2：编译检查**

```bash
python -m compileall -q src tests
```

预期：无输出，退出码为 0。

- [ ] **Step 3：运行完整测试**

```bash
python -m pytest
```

如果旧的 `word_count` 失败仍存在，最终报告写：

```text
新增题材感知分析测试已通过；完整测试仍有既存 word_count 失败。
```

## 推荐执行顺序

1. Phase 0：确认测试基线。
2. Phase 1：profile YAML 与 loader。
3. Phase 2：profile resolver。
4. Phase 2.5：运行模式与时间预算配置。
5. Phase 3：prompt builder。
6. Phase 4：insight validator。
7. Phase 5：批量 `nm pipeline insights`，并接入 `full/continue/status`。
8. Phase 6：`nm validate insights`。
9. 用 GLM 5.0 和 Qwen 3.6 Plus 各跑 5-10 章，手动检查生成质量、修复率、泛化评价比例和单批耗时。
10. Phase 7：YAML 搜索。
11. Phase 8：评估集。
12. Phase 9：文档。
13. Phase 10：端到端验证。

## 设计约束

- 第一期不要修改 `chapters.yaml` 结构。
- 第一期不要追求全题材覆盖，只做 `common`、`xuanhuan`、`xianxia`、`suspense`。
- 第一期所有字段设计都按 GLM 5.0、Qwen 3.6 Plus 的稳定输出能力收敛，不按最强模型设计。
- 每个 profile 必填字段数量必须少于等于 7 个；如果修复率超过 20%，优先减少字段，而不是加长 prompt。
- 输出必须证据优先：没有 evidence 的题材判断不能作为高置信结果进入搜索展示。
- 默认运行模式是 `standard`，目标是无人值守 5-8 小时完成主流程。
- `insights` 默认必须批量执行，`LLM_INSIGHT_BATCH_SIZE` 初始值为 20；禁止全书默认一章一调用。
- `deep insights` 不阻塞 `standard` 的 finalized；只在 `deep` 模式或手动命令中执行。
- 如果 `standard` 模式下 insights 让总耗时增加超过 30%，先把 `INSIGHTS_DEFAULT_DEPTH` 降到 `core` 并提高批量大小到 30，再考虑减少字段。
- Profile loader、resolver、prompt builder、validator、YAML 搜索测试不能依赖 PostgreSQL。
- 不要在确定性评估集之前引入 LLM judge。
- 保留 `--profile` 显式覆盖，方便调试和人工实验。
