---
name: refine
description: 事件完成后精调 outline/、worldbuilding/、characters/ 文件夹，建立交叉引用和精确弧线
when_to_use: 所有事件拆分完成后，用事件数据反哺精调早期产出物
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

在所有 events 完成后，利用事件级数据精调 `outline/`、`worldbuilding/`、`characters/`、`tags.yaml`。

**精调原则：不是增量，而是调整。可以删除、合并、重构，不无限膨胀。**

**不读原文，只读 event YAML 数据。**

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 status 为 `complete` 或 `tagged`
2. 确认 `events/` 目录下有事件文件
3. 确认文件夹结构已存在：
   - `outline/_index.yaml` + 各模块
   - `characters/_index.yaml` + `relations.yaml` + `profiles/`
   - `worldbuilding/_index.yaml` + 各模块
4. 确认 `tags.yaml` 已存在

如存在 `events_manifest.yaml`，优先读取 manifest 而非逐个读 event 文件。

## 精调操作类型

refine 支持多种操作类型，核心是"调整而非增量"：

| 操作类型 | 说明 | 适用场景 |
|----------|------|----------|
| `enrich` | 补充细节 | 有事件证据，填补空白字段 |
| `adjust` | 调整已有内容 | 发现不一致或描述不准确 |
| `merge` | 合并冗余 | 发现同义势力/人物/术语 |
| `split` | 拆分过粗内容 | 单文件内容过于复杂 |
| `delete` | 删除错误/冗余 | 无证据支撑或明确错误 |
| `restructure` | 重构结构 | 龙套升格配角、结构调整 |

**所有操作必须基于事件证据，不能凭空添加或删除。**

## 执行步骤

### 0. 检测变化 + 备份

#### 0a. 计算上次 refine 的 hash

读取 `meta.yaml` 中 `pipeline.refine_hash`（上次 refine 时事件数据的 hash）。

计算当前事件数据的 hash：
```python
# 遍历 events/ 下所有 yaml 文件，计算内容 hash
current_hash = hash_events_directory()
```

比对：
- hash 相同 → 无变化，跳过精调，报告"无需更新"
- hash 不同 → 有变化，执行精调

#### 0b. 备份待修改文件

精调会修改多个关键文件，修改前为文件夹创建备份：

```bash
# 备份文件夹结构
cp -r outline/ outline.bak/
cp -r characters/ characters.bak/
cp -r worldbuilding/ worldbuilding.bak/
cp tags.yaml tags.yaml.bak
```

备份仅保留最近一次（覆盖旧 `.bak`）。

### 1. 采集事件数据

从所有 event YAML 中提取：

#### 1a. 基础数据采集

- 每个事件的 `tension_peak` 值 → 按章聚合
- 所有 `plot_threads`（如有）→ 按 thread_id 聚类
- 每个事件的 `characters` → 人物出场统计
- 每个事件的 `character_moment` → 人物转变节点
- 每个事件的 `relationship` + `interaction` → 关系演变数据
- 每个事件的 `setting` → 地点出场统计

#### 1b. 钩子数据采集

| 来源 | 字段 | 说明 |
|------|------|------|
| 事件 hooks 字段 | `hooks.chapter_end` | 章末悬念（悬念铆合） |
| 事件 hooks 字段 | `hooks.items_crossing` | 跨事件道具（因果铆合） |
| 事件 hooks 字段 | `hooks.character_crossing` | 人物关联（反转铆合） |
| 事件 hooks 字段 | `hooks.info_hint` | 信息钩子疑似 |
| 事件 plot_function | `伏笔埋设` | 反转铆合埋设点 |
| 事件 plot_function | `伏笔回收` | 反转铆合回收点 |

**注意**：事件数量可能很大，优先依赖 `events_manifest.yaml`，必要时分批读取原始事件文件。

### 2. 钩子验证与铆合链建立

更新 `outline/hooks_network.yaml`。

#### 2a. 钩子数据合并

合并两个来源的钩子数据（事件 hooks 字段 + plot_function 反转铆合）。

#### 2b. 埋设-回收匹配

执行埋设点与回收点匹配，建立铆合链。

**匹配规则**：
- 同一 hook_type + 同一元素（道具名/人物名/信息关键词）
- 建立 chain：planted → harvested

#### 2c. 置信度验证与调整

| 原置信度 | 验证结果 | 操作 |
|----------|----------|------|
| high | 已验证回收 | 保持 high |
| high | 未找到回收 | 降为 medium + 标记 pending |
| medium | 已验证回收 | 升为 high |
| medium | 未找到回收 | 降为 low + 标记 pending |
| low | 已验证回收 | 升为 medium |
| low | 未找到回收 | **delete**（无证据） |

#### 2d. 更新 hooks_network.yaml

写入铆合链：
```yaml
chains:
  - hook_id: hook_001
    hook_type: 道具钩子
    crossing_type: 因果铆合
    planted:
      event: ev_001
      chapter: 3
      description: ...
    harvested:
      event: ev_005
      chapter: 50
    confidence: high

pending:
  - hook_id: hook_002
    ...
    confidence: medium

stats:
  total_hooks: 45
  verified_hooks: 38
  pending_hooks: 7
```

#### 2e. 更新 _index.yaml 的钩子统计

更新 `outline/_index.yaml` 中的 `hooks_stats`。

### 3. 精调 outline/ 文件夹

#### 3a. 更新 structure.yaml

- 用事件 tension 均值校准 `structure.yaml` 中各幕/序列的节奏特征
- 从 `plot_function: 转折/反转` 事件校准 `turning_point`

#### 3b. 更新 pacing_curve.yaml（如启用）

用事件 tension 数据生成/更新节奏曲线：
```yaml
tension_curve:
  - chapter: 1
    tension: 2.0
    beat_type: setup
  - chapter: 10
    tension: 3.5
    beat_type: inciting_incident
  # ...
```

#### 3c. 更新 plotlines.yaml（如启用）

用事件的 `plot_threads` 数据校准情节线索：
- 各线索的起点/转折/高潮/收束章节
- 与事件的交叉引用

#### 3d. 更新 _index.yaml

更新概览和统计：
- `structure_summary` 的章节数、转折点数
- `plotlines_summary`（如启用）
- `hooks_stats`

### 4. 精调 characters/ 文件夹

#### 4a. 更新 _index.yaml

- 用事件人物出场统计校准 `roster` 中各角色的 `first_appearance`
- 补充 `appearance_count`（出场次数）
- 补充 `active_chapters`（活跃章节范围）
- 更新 `relations_summary` 的核心关系
- 更新 `stats`（人物总数、关系总数）

**操作类型判断**：
- 发现新角色（事件中出现但 `_index.yaml` 缺失）→ `enrich`：补充到 roster
- 发现角色定位不一致 → `adjust`：校准 role/archetype
- 发现同义角色名 → `merge`：合并，删除冗余
- 发现角色从未出场（无事件关联）→ `delete`：从 roster 移除

#### 4b. 更新 relations.yaml

用事件关系数据更新关系网：
- 补充 `evolution` 轨迹（如有变化）
- 补充 `trigger_event`（关系变化触发事件）
- 校准关系类型

**操作类型判断**：
- 发现新关系 → `enrich`：补充到 relations
- 发现关系描述不准确 → `adjust`：修正描述
- 发现关系从未演变且不重要 → 评估是否 `delete`

#### 4c. 更新人物小传（profiles/）

对每个有 `file` 字段的角色（主角/重要配角）：

**key_events 交叉引用补充**：
```yaml
key_events:
  - event_id: nm_xxx_ch01_ev001
    chapter: 1
    description: "首次出场，回忆红岸基地"
    significance: "人物起点"
    role_in_event: 主角
  - event_id: nm_xxx_ch08_ev003
    chapter: 8
    significance: "核心转变"
  # ... 只记录关键节点，≤ 10 个
```

**弧线细化**：
用事件的 `character_moment` 补充弧线节点：
```yaml
arc:
  stages:
    - stage: 起点
      chapter: 1
      event: ev_001
      moment_type: 性格展示
    - stage: 转折
      chapter: 15
      event: ev_008
      trigger: "发现真相"
      moment_type: 信念崩塌
```

**心理维度补充**（基于事件证据）：
```yaml
psychology:
  fatal_flaw: "对人类的绝望导致背叛"  # 从道德抉择失误推断
  obsession: "寻找更高等文明来拯救"   # 从持续追求推断
  # 只补充有证据的字段，标记 source: refine
```

**操作类型判断**：
- 缺少 key_events → `enrich`：补充
- key_events 指向不存在的事件 → `adjust`：修正或 `delete` 该引用
- 弧线节点不准确 → `adjust`：校准
- 发现龙套角色有文件但无事件关联 → `restructure`：删除文件，降为 minor

#### 4d. 处理角色升降格

根据事件出场频率和重要性：
- minor 角色出场 > 10 次且有弧线 → `restructure`：升格为 supporting，生成 profiles 文件
- supporting 角色出场 < 3 次且无弧线 → `restructure`：降格为 minor，删除 profiles 文件

### 5. 精调 worldbuilding/ 文件夹

#### 5a. 更新 _index.yaml

- 用事件地点统计校准 `regions_count`、`factions_count`
- 更新 `stats`

#### 5b. 更新 geography（单文件或文件夹）

用事件 `setting` 统计：
- 补充地点的 `key_events` 交叉引用
- 补充地点的 `first_appearance`
- 校准地点的 `significance`

**粒度判断**：
- 地点数 > 3 且为单文件 → `split`：拆为文件夹
- 地点数 ≤ 3 且为文件夹 → `merge`：合并为单文件

#### 5c. 更新 factions（单文件或文件夹）

用事件势力信息：
- 补充势力的 `key_events` 交叉引用
- 校准势力的 `relationships`
- 补充势力的成员变化（如事件中有阵营变动）

**操作类型判断**：
- 发现新势力 → `enrich`：补充
- 发现同义势力 → `merge`：合并
- 发现势力无事件关联 → `delete`：移除

#### 5d. 更新 lore/

- 补充 `history.yaml` 的历史事件与 `first_referenced`
- 补充 `artifacts.yaml` 的物品与 `key_events`
- 补充 `terminology.yaml` 的术语与 `first_appearance`

### 6. 精调 tags.yaml

基于事件标签统计校准小说级标签：
- 主导 event_type 分布 → 校准 `dominant_event_types`
- 主导 emotion 分布 → 校准 `emotional_profile`
- technique 分布 → 校准 `craft_profile`

### 7. 清理已删除事件的引用

检查所有文件，删除指向不存在事件的引用：
- 人物小传的 `key_events` 中无效 event_id → 删除
- 势力/地点的 `key_events` 中无效 event_id → 删除
- 钩子的 `planted.event` / `harvested.event` 无效 → 删除或标记 pending

### 8. 更新 SQLite 索引

调用 `build-index` 更新 SQLite 表：
- 更新 `characters` 表的 `appearance_count`、`file_path`
- 更新 `factions` 表
- 更新 `regions` 表
- 新增 `character_events`、`faction_events` 交叉引用表

### 9. 标记精调完成

更新 `meta.yaml`：
```yaml
pipeline:
  refined: true
  refined_at: "2026-04-21T12:00:00Z"
  refine_hash: "{当前事件数据hash}"
  refine_summary:
    operations:
      enrich: {n}
      adjust: {n}
      merge: {n}
      split: {n}
      delete: {n}
      restructure: {n}
    hooks_verified: {n}
    hooks_pending: {n}
    key_events_added: {n}
    characters_enriched: {n}
    worldbuilding_enriched: {n}
```

## 输出格式

```
✅ 精调完成

📚 素材：{name}

精调操作统计：
  enrich：{n} 次   # 补充细节
  adjust：{n} 次   # 调整内容
  merge：{n} 次    # 合并冗余
  split：{n} 次    # 拆分过粗
  delete：{n} 次   # 删除无效
  restructure：{n} 次 # 重构结构

文件夹更新：
  📂 outline/
    - hooks_network.yaml：验证 {n} 条钩子，{n} 条待回收
    - structure.yaml：校准转折点
    - pacing_curve.yaml：补充 {n} 个数据点
    - _index.yaml：统计更新
  
  📂 characters/
    - _index.yaml：{n} 角色更新，{n} 升格，{n} 降格
    - relations.yaml：{n} 条关系更新
    - profiles/*.yaml：{n} 个小传补充 key_events
  
  📂 worldbuilding/
    - _index.yaml：统计更新
    - geography/：{n} 地点补充 key_events
    - factions/：{n} 势力校准
    - lore/：术语/物品补充
  
  🏷️ tags.yaml
    - 标签校准：{n} 个维度

后续操作：
  /novel-stats {id}    # 生成统计报告
```

## 注意事项

- **精调是调整而非增量**：可以删除、合并、重构，不无限膨胀
- **所有操作基于事件证据**：无证据不添加，有矛盾则调整
- **key_events 只记录关键节点**：≤ 10 个，避免膨胀
- **删除无效引用**：指向不存在事件的引用必须清理
- **粒度自适应**：≤ 3 用单文件，> 3 用文件夹，可动态调整
- **不读原文**：只依赖 event YAML 数据
- **备份先行**：修改前备份文件夹结构
- **hash 检测变化**：无变化时跳过，避免重复工作
- 事件文件过多时，优先依赖 manifest，必要时分批读取
- 钩子验证采用保守策略：不确定时标 pending，无证据则删除

## References

- [outline.schema.yaml](../../../docs/schemas/outline.schema.yaml)
- [worldbuilding.schema.yaml](../../../docs/schemas/worldbuilding.schema.yaml)
- [characters.schema.yaml](../../../docs/schemas/characters.schema.yaml)
- [novel-tags.schema.yaml](../../../docs/schemas/novel-tags.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)