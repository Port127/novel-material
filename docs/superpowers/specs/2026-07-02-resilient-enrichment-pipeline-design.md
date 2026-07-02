# 长篇素材增强阶段抗失败设计

## 背景

`nm_novel_20260701_7u96` 暴露出增强阶段在长篇素材上的共同弱点：

- `characters` 生成了人物档案，但核心人物完整小传全部降级为统计兜底。
- `worldbuilding` 单次大调用超时后写入空结构，实体、关系和证据全为 0。
- `profile` 返回内容未通过 schema 校验，最终没有写出 `work_profile.yaml`。
- `insights` 只保存了少量成功章节，大量漏章和 schema 错误缺少细粒度补救。
- `validate` 和 `release_gate` 能发现失败，但 next action 不够具体，无法指导最省 API 的修复路径。

这些问题的根因不是某一本素材，而是增强阶段过于依赖“一次大调用 + 严格整体验证”。本设计目标是让长篇素材在 LLM 超时、输出漏字段、局部 schema 漂移时仍保留可用产物，并把不可用部分限定在最小范围。

## 目标

- 将 `characters` 改为小批次、分层 schema、逐人物 repair 和局部保留。
- 将 `worldbuilding` 改为分维度抽取、维度级 repair 和统计兜底。
- 为 `profile` 增加独立 timeout、降级生成和 evidence repair。
- 将 `insights` 改为小批次、缺章单独补、schema 错误单章 repair。
- 让 LLM timeout 上限可配置，避免 SDK 层 300 秒封顶限制大任务。
- 让报告和发布门禁展示可执行的质量分布和修复路径。
- 减少重复 API 消耗：成功的局部产物必须保存，失败只重试失败单元。

## 非目标

- 不在本设计中重跑或修补历史素材。
- 不降低 `standard` 模式的可发布质量要求。
- 不改变 embedding 维度，不做数据库大迁移。
- 不把统计兜底伪装成完整 LLM 分析。
- 不让 `--allow-degraded-sync` 成为默认路径。

## 总体方案

采用“分层产物 + 小批次 + repair + 局部失败保留”的方案。

```text
LLM 原始输出
  -> 结构化解析
  -> 单元级校验
  -> 单元级 repair
  -> 质量分级保存
  -> audit/report/release_gate 汇总
```

单元的含义按阶段区分：

- `characters`：单个人物。
- `worldbuilding`：单个世界观维度或单条关系。
- `profile`：作品画像子结构和证据索引。
- `insights`：单章 insight。

核心原则：

- 成功单元立即保存，不因同批其他单元失败而丢弃。
- 严格字段缺失才阻断该单元，非核心字段进入 repair 或补默认值。
- repair 失败后保存 `partial` 或 `stats_seeded`，并记录 `schema_issues`。
- 报告展示质量分布，而不是只给一个成功或失败结论。

## Characters 设计

### 批次策略

新增配置：

```yaml
LLM_CORE_CHARACTER_BATCH_SIZE: 2
LLM_SUPPORTING_CHARACTER_BATCH_SIZE: 12
LLM_MINOR_CHARACTER_BATCH_SIZE: 20
LLM_CHARACTER_REPAIR_MAX_ATTEMPTS: 1
```

核心人物默认 2 人一批。支持和次要人物继续使用较大批次，因为它们只要求简档，不要求完整小传。

### Schema 分层

严格字段：

```text
name
role
description
narrative_function
first_appearance_chapter
appearance_count
key_events
confidence
```

可修复字段：

```text
arc_summary
psychology
relationships
external_goal
internal_need
speech_style
```

宽松字段：

```text
habits
interaction_patterns
craft_notes
key_scenes
moral_spectrum
archetype
basis
```

严格字段缺失时进入 repair；可修复字段缺失时可补空值并降级；宽松字段不阻断保存。

### 质量等级

人物档案新增或标准化以下等级：

```text
full       严格字段和主要可修复字段均合格
enriched   严格字段合格，少量重要字段缺失或由 repair 补齐
partial    严格字段基本可用，但仍存在 schema_issues
fallback   仅由统计兜底生成
```

`biography_complete: true` 只给 `full`。`enriched` 和 `partial` 必须保存，但不计入完整小传完成数。

### Repair 流程

```text
批次 LLM 返回
  -> 拆成人物候选
  -> 逐人物 normalize
  -> 失败人物进入 repair prompt
  -> repair 成功保存 full/enriched
  -> repair 失败保存 partial 或 fallback
```

repair 输入必须包含：

- 原始人物 JSON。
- 具体错误列表。
- 目标人物姓名和候选名单。
- 分层字段要求。

禁止因单个人物 repair 失败丢弃整批结果。

### 产物诊断

人物 YAML 增加诊断字段：

```yaml
profile_level: enriched
biography_complete: false
source_quality: llm_repaired
repair_attempts: 1
schema_issues:
  - relationships 缺失，已补为空数组
```

`characters/_index.yaml` 增加：

```yaml
quality_counts:
  full: 0
  enriched: 0
  partial: 0
  fallback: 0
repair_counts:
  attempted: 0
  succeeded: 0
  failed: 0
```

## Worldbuilding 设计

### 分维度抽取

`worldbuilding` 不再只依赖一次全书大调用。新流程：

```text
章节分析 + 大纲 + 统计候选
  -> 维度路由
  -> 按维度构建上下文
  -> 维度级 LLM 抽取 entities/relations/evidence
  -> 维度级 normalize 和 repair
  -> 合并 layered worldbuilding
```

首批维度：

```text
organizations
locations
power_system
rules
resources
history_events
concepts
```

每个维度独立记录状态：

```yaml
dimension_status:
  organizations: llm_verified
  locations: llm_repaired
  power_system: not_applicable
  rules: stats_seeded
  resources: missing
```

### Stats Seeded 兜底

章节分析中已有组织、地点、人物出场和部分设定线索。LLM 失败时，高频组织和地点应写入 `stats_seeded` 实体，而不是写空世界观。

`stats_seeded` 实体必须保守：

```yaml
source_quality: stats_seeded
description: 从章级分析统计生成的基础实体，待 LLM 补全
confidence: 0.45
evidence:
  - chapter: 1
    basis: fact
    summary: 章级分析中出现该实体
```

统计兜底不能生成复杂关系，只能生成实体和最基本出现证据。

### Schema 分层

实体严格字段：

```text
name
type
description
importance
evidence
confidence
```

可修复字段：

```text
properties
key_appearances
first_appearance_chapter
relations
```

宽松字段：

```text
dimension_tags
narrative_function
inference_notes
```

关系的 `source/target` 若无法匹配实体，优先 repair；repair 后仍无法匹配时丢弃该关系并记录 `broken_relation_count`，不使整个维度失败。

### 状态语义

- 有适用维度且所有适用维度都失败：`failed` 或门禁阻断。
- 部分维度失败但有可用实体：`degraded`。
- 不适用维度明确标记 `not_applicable`：不算失败。
- 只有空结构且 `llm_success: false`：不得标记为 success。

## Profile 设计

### 输入范围

`profile` 只读取稳定产物，不读取完整原文：

- `meta.yaml`
- `tags.yaml`
- `outline/`
- 关键章节摘要
- `characters` 中 `full/enriched/partial` 的紧凑摘要
- `worldbuilding` 中 `llm_verified/llm_repaired/stats_seeded` 的实体摘要

如果前置产物不足，也应生成有限作品画像，并在 `limitations` 中说明。

### Timeout 配置

新增：

```yaml
LLM_PROFILE_TIMEOUT: 1800
```

`config_service.py` 必须将其暴露为 `config["llm"]["profile_timeout"]`。

### Schema 放松

严格字段：

```text
core_hooks
reader_expectations
story_structure
evidence_index
confidence
limitations
```

可为空字段：

```text
motifs_and_techniques
transferable_lessons
worldbuilding_drivers
character_dynamics
```

`evidence_index` 缺失时进入 repair。repair 后仍证据不足时允许写出：

```yaml
quality_level: limited
limitations:
  - 核心人物小传部分为 partial
  - 世界观部分维度来自统计兜底
```

`work_profile.yaml` 不作为事实来源；它只作为写作 Agent 的作品级入口。

## Insights 设计

### 批次策略

新增或调整：

```yaml
LLM_INSIGHT_BATCH_SIZE: 5
LLM_INSIGHT_REPAIR_MAX_ATTEMPTS: 1
```

`standard` 模式仍可只处理前 100 章或关键章节集合，但每批规模降低，减少漏章影响面。

### 缺章与 Schema Repair

```text
批次返回
  -> 保存合格章节
  -> missing chapters 单章补
  -> schema invalid 章节单章 repair
  -> repair 失败记录 failed，不影响已保存章节
```

报告展示：

```yaml
insight_quality:
  expected: 100
  succeeded: 0
  repaired: 0
  failed: 0
  missing_after_repair: 0
```

## LLM Timeout 与调用层

当前调用层存在单次 SDK timeout 封顶：

```python
sdk_timeout = min(total_timeout * 0.8, 300)
```

新增配置：

```yaml
LLM_SDK_TIMEOUT_CAP: 1200
LLM_WORLDBUILDING_TIMEOUT: 3600
LLM_CHARACTERS_TIMEOUT: 1800
LLM_INSIGHTS_TIMEOUT: 1200
LLM_PROFILE_TIMEOUT: 1800
```

调用层规则：

- `sdk_timeout = min(total_timeout * 0.8, sdk_timeout_cap)`。
- 阶段可以覆盖 `timeout_override`。
- 超时诊断必须记录 `total_timeout`、`sdk_timeout`、`attempt_count` 和 `context`。
- 对大对象阶段，timeout 后优先缩小任务单元，不优先整阶段重跑。

## Validate 与 Release Gate 设计

### 标签字典问题

`chapter_functions` 等生成标签必须先做 canonical 映射：

```text
LLM 标签
  -> 字典精确匹配
  -> synonym 匹配
  -> unknown_tags
```

`unknown_tags` 默认进入 warning 或 review item，不直接制造数千个 hard error。只有核心受控标签字段无法映射且影响检索契约时才作为 error。

### 门禁分级

```text
blocker：章节覆盖缺失、核心事实文件无法读取、schema 损坏无法解析
error：worldbuilding 全空、核心人物全 fallback、profile 缺失
warning：部分 insights 缺失、部分标签 unknown、部分维度 stats_seeded
```

`release_gate` 输出必须包含最省 API 的 next actions：

```text
1. repair characters core biographies
2. repair worldbuilding organizations/locations/rules
3. regenerate profile
4. rerun audit
```

## 实施阶段

### 第一阶段：减少 API 浪费

- `characters` 小批次。
- 人物分层 normalize。
- 人物逐个 repair 和 partial 保存。
- timeout cap、profile timeout 配置。
- 报告展示人物质量分布。

### 第二阶段：世界观抗失败

- `worldbuilding` 分维度抽取。
- `stats_seeded` 实体兜底。
- 维度级 repair。
- 合并与审计质量分级。

### 第三阶段：收尾质量

- `profile` 降级生成和 evidence repair。
- `insights` 小批次和单章 repair。
- `validate/release_gate` 分级和 next actions。

## 验收标准

- 核心人物批次中一个人物 schema 失败时，同批其他人物仍被保存。
- 核心人物 repair 后可产生 `full/enriched/partial/fallback` 分布，而不是全部 fallback。
- `worldbuilding` 单个维度超时不会清空整个世界观。
- LLM 失败时，高频组织和地点可生成 `stats_seeded` 实体。
- `profile` 在前置产物部分降级时仍可写出 `quality_level: limited` 的作品画像。
- `insights` 批次漏章时已成功章节不丢失，漏章进入单章 repair。
- `release_gate` 报告能指出具体修复阶段和优先级。
- 单元测试不调用真实 LLM、不连接真实数据库、不修改真实素材。

## 风险与缓解

- 风险：schema 放松导致低质量内容被误认为完整。
  缓解：用 `profile_level`、`source_quality`、`schema_issues` 和门禁分级区分质量。
- 风险：repair 增加 API 成本。
  缓解：只 repair 失败单元，成功单元立即保存；repair 次数默认 1。
- 风险：worldbuilding 分维度后关系重复或冲突。
  缓解：合并阶段统一实体 ID 和关系去重，无法匹配的关系记录后丢弃。
- 风险：`stats_seeded` 被误用为事实丰富世界观。
  缓解：降低 confidence，写明来源，仅用于基础检索和后续 repair 种子。
- 风险：发布门禁过严导致素材长期无法同步。
  缓解：输出最小修复路径；人工放行仍需显式参数，并记录 override。
