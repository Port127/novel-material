# 分层世界观与作品画像设计

## 1. 背景

第二期已经完成前置导航、`--window` 解耦、主要人物选择、完整小传和定向修复。剩余的第三期问题集中在世界观和作品级入口：

1. `worldbuilding` 仍由一次 LLM 调用抽取固定四类结构，容易把都市、悬疑、仙侠等题材强行塞进同一 schema。
2. 当前世界观产物缺少稳定实体 ID、章节证据、关系文件和题材维度说明。
3. 搜索与同步层只理解旧的 `factions / regions / power_systems` 形态，尚未适配新世界观结构。
4. 缺少 `work_profile.yaml` 作为写作 Agent 的作品级入口，导致 Agent 想理解“这本书为什么可借鉴”时仍需散读章节、人物、世界观和标签。

第三期的核心目标不是立刻证明检索质量提升，而是把世界观事实结构和作品画像契约做扎实，使后续检索评测和写作 Agent 能基于更完整、可追溯的材料工作。

## 2. 目标与非目标

### 2.1 目标

- 将世界观升级为题材自适应的分层产物，包含概览、维度、实体、关系和章节证据。
- 保持旧世界观四文件可读：`power_system.yaml`、`geography.yaml`、`factions.yaml`、`lore.yaml`。
- 增加 `work_profile.yaml`，作为写作 Agent 的作品级入口，但不替代下层事实文件。
- 将新世界观结构接入审计、报告、存储同步、embedding 和搜索读取路径。
- 支持断点续传和跨会话执行，每个 implementation packet 可独立验证和提交。
- 默认测试不调用真实 LLM、不连接真实数据库、不修改真实素材；真实素材只做显式授权的只读 smoke。

### 2.2 非目标

- 不建设完整小说知识图谱。
- 不引入无界数据库迁移；若关系需要新表，必须在实施计划中单独设计 migration 和回退。
- 不改变 embedding 维度。
- 不声称世界观或人物检索质量已经提升，除非后续 Golden Query 人工基线证明。
- 不在审计或报告阶段自动修复事实 YAML。

## 3. 推荐方案

采用“契约优先、渐进接入”的方案：

1. 先定义新世界观 YAML 契约和旧格式兼容读取器。
2. 再做题材维度路由和 LLM 响应归一化。
3. 然后写入新 `worldbuilding/` 结构，并让审计能识别新旧结构的质量状态。
4. 接着增加 `profile` 阶段，输出 `work_profile.yaml`。
5. 最后适配 embedding、storage 和 search。

这个顺序牺牲了一点端到端速度，但能把风险切薄：每一步都能在没有真实 LLM 和真实数据库的情况下验证。

## 4. 世界观目录与契约

新世界观目录：

```text
worldbuilding/
├── _index.yaml
├── overview.yaml
├── dimensions.yaml
├── entities/
│   └── *.yaml
└── relations.yaml
```

### 4.1 `_index.yaml`

`_index.yaml` 是世界观产物摘要，不是完整事实源。

```yaml
schema_version: 2.0.0
layout: layered
dimension_count: 0
entity_count: 0
relation_count: 0
evidence_count: 0
legacy_compatible: true
llm_success: true
created_at: "2026-06-30T00:00:00"
```

旧世界观 `_index.yaml` 没有 `layout: layered` 时按 legacy 读取。读取器必须返回统一视图，但不得在读取时改写旧文件。

### 4.2 `dimensions.yaml`

`dimensions.yaml` 记录本书适用和不适用的世界观维度。

```yaml
schema_version: 1.0.0
source:
  navigation_dimensions: ["商业环境", "校园关系"]
  genre_profiles: ["common", "urban"]
dimensions:
  - id: business_rules
    name: 商业规则
    category: social
    applicability: applicable
    reason: 主线围绕创业、投资和企业竞争展开
    confidence: 0.82
  - id: cultivation_levels
    name: 修炼等级
    category: power
    applicability: not_applicable
    reason: 章级事实和前置导航都未出现超自然力量体系
    confidence: 0.91
```

`not_applicable` 是合法结论，不构成质量失败。

### 4.3 `overview.yaml`

`overview.yaml` 解释世界如何运转，不重复堆实体。

```yaml
schema_version: 1.0.0
world_summary: ""
driving_mechanisms:
  - mechanism: ""
    description: ""
    related_dimensions: []
    evidence:
      - chapter: 1
        summary: ""
confidence: 0.0
limitations: []
```

### 4.4 `entities/*.yaml`

每个实体一个文件，文件名使用稳定 slug，实体内部保留显示名。

```yaml
schema_version: 1.0.0
id: faction_jiangling_university
type: organization
name: 江陵大学
aliases: []
description: ""
properties: {}
importance: primary
first_appearance_chapter: 1
key_appearances:
  - chapter: 1
    role: 初始环境
evidence:
  - chapter: 1
    basis: fact
    summary: ""
confidence: 0.0
```

实体类型使用开放枚举，但首批路由至少覆盖：

- `organization`
- `location`
- `rule`
- `resource`
- `power_system`
- `social_system`
- `history_event`
- `concept`

### 4.5 `relations.yaml`

关系文件记录实体之间的结构关系和演化关系。

```yaml
schema_version: 1.0.0
relations:
  - id: rel_0001
    source_id: faction_a
    target_id: location_b
    relation_type: located_in
    description: ""
    evolution:
      - chapter_range: [1, 20]
        state: ""
    evidence:
      - chapter: 3
        basis: fact
        summary: ""
    confidence: 0.0
```

关系类型首批覆盖：

- `located_in`
- `belongs_to`
- `allied_with`
- `conflicts_with`
- `depends_on`
- `constrains`
- `evolves_to`
- `interacts_with`

## 5. 题材维度路由

维度路由由三类信号合并：

1. 前置导航 `evaluation.yaml` 的 `worldbuilding_dimensions`。
2. `meta.yaml` 题材和现有 analysis profile。
3. 章级分析聚合出的地点、组织、规则、资源等信号。

路由原则：

- 先判断适用维度，再要求 LLM 填实体。
- 不因都市小说没有修炼等级而报错。
- 不因玄幻小说缺少商业规则而报错。
- 对低置信度维度保留 `confidence` 和 `reason`，供审计与报告展示。

建议首批内置维度 profile：

| profile | 适用题材 | 默认维度 |
|---|---|---|
| `common` | 全部 | 组织网络、地点、制度规则、历史背景、核心概念 |
| `urban` | 都市、重生、现实向 | 时代环境、商业规则、社会阶层、法律制度、校园/职场网络 |
| `xuanhuan` | 玄幻 | 力量体系、资源、势力、地理、历史、禁忌 |
| `xianxia` | 仙侠 | 修炼体系、宗门结构、资源、地域层级、因果/天道规则 |
| `suspense` | 悬疑 | 空间结构、制度环境、秘密组织、信息规则、案件背景 |

## 6. `work_profile.yaml`

`profile` 阶段读取稳定分析产物，不重新读取全书原文。

输入：

- `meta.yaml`
- `evaluation.yaml`
- `chapters.yaml`
- `outline/`
- `characters/`
- `worldbuilding/`
- `tags.yaml`
- `chapter_insights/`，若存在

输出：

```yaml
schema_version: 1.0.0
material_id: nm_xxx
title: ""
core_hooks: []
reader_expectations: []
story_structure:
  pacing_pattern: ""
  turning_point_pattern: []
character_dynamics:
  ensemble_summary: ""
  key_relationship_patterns: []
worldbuilding_drivers:
  - mechanism: ""
    narrative_function: ""
motifs_and_techniques: []
transferable_lessons:
  - lesson: ""
    applies_when: ""
    avoid_when: ""
evidence_index:
  chapters: []
  characters: []
  worldbuilding_entities: []
limitations: []
confidence: 0.0
```

`work_profile.yaml` 是作品级入口，不是事实源。需要证据时，外部 Agent 仍应读取或检索下层章节、人物和世界观产物。

## 7. Pipeline 与 CLI

新增 `profile` 阶段：

```text
ingest
  ↓
evaluate
  ↓
analyze → insights
  ↓
outline / worldbuilding / characters / tags
  ↓
refine
  ↓
profile
  ↓
artifact audit
  ↓
storage sync
```

新增命令：

```bash
nm pipeline profile nm_xxx
```

`full` 和 `continue` 在 `standard/deep` 中默认执行 `profile`。`fast` 可以跳过 `profile`，但必须在报告中说明作品画像缺失。若旧素材已有前序产物，可以单独执行 `nm pipeline profile nm_xxx`，不强制重跑章级分析。

## 8. 审计与报告

世界观审计新增质量信号：

- `worldbuilding_missing_layered_index`：新布局缺少 `_index.yaml` 或 schema 无法识别。
- `worldbuilding_empty_applicable_dimension`：适用维度没有实体、概览或不适用说明。
- `worldbuilding_entity_missing_evidence`：主要实体缺少章节证据。
- `worldbuilding_relation_unknown_entity`：关系引用不存在的实体 ID。
- `work_profile_missing`：标准/深度模式缺少作品画像。
- `work_profile_low_evidence`：作品画像没有引用下层证据。

审计保持只读。它可以给出下一步命令，但不得修复 YAML。

## 9. Storage、Embedding 与 Search

### 9.1 兼容读取

存储层先通过统一读取器获得世界观实体：

- 新结构：读取 `entities/*.yaml`。
- 旧结构：继续读取 `factions.yaml`、`geography.yaml`、`power_system.yaml` 等文件并适配为实体视图。

### 9.2 同步策略

首批优先复用现有 `worldbuilding_entities` 表：

- `entity_type` 映射新实体 `type`。
- `name` 使用实体显示名。
- `description` 使用实体描述。
- `properties` 保存属性、证据摘要、维度 ID、关系摘要等扩展字段。
- `first_appearance` 使用 `first_appearance_chapter`。

关系如果需要结构化查询，再单独增加 `worldbuilding_relations` migration。第三期计划中应把“复用 properties”和“新增关系表”拆成独立 packet，避免 migration 风险污染世界观生成阶段。

### 9.3 搜索适配

搜索层目标是“能查新结构且不破坏旧查询”：

- `nm search world` 继续支持旧的 `--dimension factions/regions/power_systems`。
- 新实体类型可通过同一过滤参数查询。
- 返回 metadata 中增加 `entity_id`、`evidence`、`dimension_ids` 和 `relation_summaries`。
- 未完成人工检索基线前，文档和报告只说“结构更完整、可检索字段更多”，不说“搜索质量提升”。

## 10. 兼容与迁移

- 旧世界观文件只读兼容，不在读取时自动改写。
- 新世界观生成会写入 layered 布局；是否保留旧四文件由实施计划决定，但不得让旧同步和旧搜索失效。
- `status` 和 `continue` 需要识别 `profile` 阶段。
- 已完成旧流水线的素材可以单独运行 `worldbuilding` 或 `profile`，不强制重跑 `analyze`。
- 真实素材 LLM 修复或重跑必须单独授权。

## 11. 测试策略

默认测试必须无网络、无真实数据库、无真实 LLM。

单元测试：

- 世界观新旧格式读取器。
- 题材维度路由。
- LLM 响应 normalize/validate。
- 实体 slug、证据引用和关系引用校验。
- `work_profile.yaml` normalize/validate。

集成测试：

- 小型固定素材写入 layered 世界观结构。
- `profile` 阶段读取下层产物并生成作品画像。
- `continue` 能从缺失 `profile` 阶段恢复。
- 审计识别新世界观缺证据、关系断链和作品画像缺失。

存储与搜索测试：

- 新旧世界观结构都能同步为 `worldbuilding_entities`。
- embedding 构造文本包含实体描述、属性和证据摘要。
- `search world` 返回新 metadata 且旧过滤参数不破坏。

真实 smoke：

- 只读运行 `validate artifacts` 和必要的报告重建。
- 若执行真实 `worldbuilding/profile` LLM，必须提前记录授权、模型、耗时、Token 和事实文件差异。

## 12. 分包执行建议

第三期实施计划建议拆成 11 个 packet：

1. 第三期执行状态目录和 packet 索引。
2. 世界观契约模型与旧格式兼容读取。
3. 题材维度路由。
4. 世界观 LLM 输出 normalize/validate。
5. 写入 layered `worldbuilding/` 结构。
6. 世界观审计与报告质量信号。
7. `work_profile.yaml` 契约。
8. `profile` 阶段与 CLI/orchestrator/status/continue 接入。
9. embedding 与 storage 兼容新世界观。
10. `search world` 适配新实体 metadata。
11. 权威文档、全量验证和真实只读 smoke。

每个 packet 都必须更新执行 STATE，并在中断时记录当前 packet、最近验证、最后可用提交和已知脏文件。

## 13. 验收标准

- 新写入的世界观产物使用 layered 布局，并包含维度、概览、实体、关系和章节证据。
- 不适用维度能被结构化表达，且不会被审计为质量失败。
- 旧世界观四文件能继续读取、同步和搜索。
- `work_profile.yaml` 能作为作品级入口引用下层证据，但不替代事实文件。
- `full/continue/status` 能识别新增 `profile` 阶段。
- 审计和报告能展示世界观实体证据、关系断链和作品画像状态。
- 默认测试不触发真实 LLM、真实数据库或真实素材改写。
- 未完成人工 Golden Query 前，不声称检索质量提升。
