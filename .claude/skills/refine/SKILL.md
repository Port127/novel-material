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

**不读原文，只读 event YAML 数据 + 精炼统计摘要（refine_input.json）。**

## 分批执行架构

refine 采用 **6 个批次分批执行**，每批完成后立即写入并更新状态，
避免一次性读全部事件导致上下文爆炸。

| 批次 | 操作 | 数据源 | 上下文控制 |
|------|------|--------|-----------|
| batch-1 | 统计数据合并 | `refine_input.json` | 只读 JSON，不读原始事件 |
| batch-2 | 钩子验证 | 钩子清单 + 涉及的少数事件 | 每次验证 10 个钩子，只读相关事件 |
| batch-3 | 人物弧线 | 人物出场统计 + profiles/ | 每次处理 5-10 个角色 |
| batch-4 | 关系验证 | relations.yaml + 涉及事件 | 每次验证 5 对关系 |
| batch-5 | 世界观精调 | 地点/势力统计 + lore/ | 只读统计 + 个别事件 |
| batch-6 | 清理汇总 | 汇总前 5 批结果 | 不读原始事件 |

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 status 为 `complete` 或 `tagged`
2. 确认 `events/` 目录下有事件文件
3. 确认 `refine_input.json` 已存在（如不存在，先运行 `extract_refine_data.py`）
4. 确认文件夹结构已存在：
   - `outline/_index.yaml` + 各模块
   - `characters/_index.yaml` + `relations.yaml` + `profiles/`
   - `worldbuilding/_index.yaml` + 各模块
5. 确认 `tags.yaml` 已存在

如存在 `events_manifest.yaml`，优先读取 manifest 而非逐个读 event 文件。

## 恢复逻辑

| 状态 | 行为 |
|------|------|
| refine_batches 缺失或 current_batch=1 | 从 batch-1 开始 |
| current_batch=2 | 从 batch-2（钩子验证）继续 |
| current_batch=3 | 从 batch-3（人物弧线）继续 |
| current_batch=4 | 从 batch-4（关系验证）继续 |
| current_batch=5 | 从 batch-5（世界观精调）开始 |
| current_batch=6 | 从 batch-6（清理汇总）开始 |
| cleanup_done=true | 输出"已完成" |

> ⚠️ batch-2/3/4 内部可能跨多轮对话（钩子数、角色数、关系数过多时）。
> 每轮完成后保持 current_batch 不变，处理下一批，直到该批次的全部数据完成。

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

### 0. 提取精炼数据 + 检测变化 + 备份

#### 0a. 提取精炼数据

如 `refine_input.json` 不存在或 `refine_hash` 与上次不同，先运行：
```bash
python scripts/core/extract_refine_data.py {material_id}
```

此脚本从所有 events/*.yaml 提取精简统计，输出约 10-50KB 的 JSON 文件。
后续批次优先读取此文件，而非逐个读原始事件。

#### 0b. 检测事件数据变化

读取 `meta.yaml` 中 `pipeline.refine_hash`（上次 refine 时事件数据的 hash）。

运行脚本获取当前 hash：
```bash
python scripts/core/extract_refine_data.py {material_id} --no-update-meta --output /tmp/current_hash.json
```

从输出 JSON 中读取 `events_hash` 字段，与 `meta.yaml` 的 `refine_hash` 比对：
- hash 相同 → 无变化，跳过精调，报告"无需更新"
- hash 不同 → 有变化，执行精调

#### 0c. 备份待修改文件

精调会修改多个关键文件，修改前为文件夹创建备份：

```bash
# 备份文件夹结构
cp -r outline/ outline.bak/
cp -r characters/ characters.bak/
cp -r worldbuilding/ worldbuilding.bak/
cp tags.yaml tags.yaml.bak
```

备份仅保留最近一次（覆盖旧 `.bak`）。

### 1. Batch-1：统计数据合并

读取 `refine_input.json`，将统计数据合并到各文件：

- 人物出场统计 → `characters/_index.yaml` 的 `appearance_count`、`active_chapters`
- tension 按章聚合 → `outline/pacing_curve.yaml`
- 地点/势力统计 → `worldbuilding/` 对应文件的出场次数
- event_type 分布 → `tags.yaml` 的 `dominant_event_types`

**不修改任何结构，只补充统计数据。**

完成后更新 `meta.yaml`：
```yaml
refine_batches:
  current_batch: 2
  batches_completed: 1
  stats_merged: true
```

### 2. Batch-2：钩子验证与铆合链建立

从 `refine_input.json` 的 `hooks` 清单中，**每次取 10 个钩子**进行验证。

#### 2a. 读取相关事件

对每个钩子：
- 从 `chapters_involved` 字段定位相关章节
- 只读涉及的少数事件原始 YAML（通常 1-3 个）

#### 2b. 埋设-回收匹配

合并两个来源的钩子数据（事件 hooks 字段 + plot_function 反转铆合）。

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

写入铆合链。

**如果还有未处理的钩子**，保持 current_batch=2，提示用户继续下一批钩子验证。

**如果全部钩子验证完成**，更新状态：
```yaml
refine_batches:
  current_batch: 3
  batches_completed: 2
  hooks_verified: true
```

### 3. Batch-3：人物弧线

从 `refine_input.json` 的 `character_appearances` 中，**每次处理 5-10 个角色**。

#### 3a. 更新 _index.yaml

- 用事件人物出场统计校准 `roster` 中各角色的 `first_appearance`
- 补充 `appearance_count`（出场次数）
- 补充 `active_chapters`（活跃章节范围）

**操作类型判断**：
- 发现新角色（事件中出现但 `_index.yaml` 缺失）→ `enrich`：补充到 roster
- 发现角色定位不一致 → `adjust`：校准 role/archetype
- 发现同义角色名 → `merge`：合并，删除冗余
- 发现角色从未出场（无事件关联）→ `delete`：从 roster 移除

#### 3b. 更新 relations.yaml

用事件关系数据更新关系网：
- 补充 `evolution` 轨迹（如有变化）
- 补充 `trigger_event`（关系变化触发事件）
- 校准关系类型

**操作类型判断**：
- 发现新关系 → `enrich`：补充到 relations
- 发现关系描述不准确 → `adjust`：修正描述
- 发现关系从未演变且不重要 → 评估是否 `delete`

#### 3c. 更新人物小传（profiles/）

对每个有 `file` 字段且在本批的角色（主角/重要配角）：

**key_events 交叉引用补充**（只记录关键节点，≤ 10 个）。

**弧线细化**：用事件的 `character_moment` 补充弧线节点。

**心理维度补充**（基于事件证据，只补充有证据的字段，标记 source: refine）。

**操作类型判断**：
- 缺少 key_events → `enrich`：补充
- key_events 指向不存在的事件 → `adjust`：修正或 `delete` 该引用
- 弧线节点不准确 → `adjust`：校准
- 发现龙套角色有文件但无事件关联 → `restructure`：删除文件，降为 minor

#### 3d. 处理角色升降格

根据事件出场频率和重要性：
- minor 角色出场 > 10 次且有弧线 → `restructure`：升格为 supporting，生成 profiles 文件
- supporting 角色出场 < 3 次且无弧线 → `restructure`：降格为 minor，删除 profiles 文件

**如果还有未处理的角色**，保持 current_batch=3，提示用户继续下一批。

**如果全部角色处理完成**，更新状态：
```yaml
refine_batches:
  current_batch: 4
  batches_completed: 3
  characters_refined: true
```

### 4. Batch-4：关系验证

从 `characters/relations.yaml` 和事件数据中，**每次验证 5 对关系**。

对每对关系：
- 从 `relations.yaml` 中取出一对关系
- 从 `refine_input.json` 的 `character_appearances` 中找出双方共同出现的事件（event_ids 交集）
- 只读相关事件原始 YAML（通常 2-5 个）
- 验证关系演变是否准确
- 更新 `evolution` 轨迹

**如果还有未验证的关系**，保持 current_batch=4。

**如果全部关系验证完成**，更新状态：
```yaml
refine_batches:
  current_batch: 5
  batches_completed: 4
  relations_verified: true
```

### 5. Batch-5：世界观精调

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
- 补充势力的成员变化

**操作类型判断**：
- 发现新势力 → `enrich`：补充
- 发现同义势力 → `merge`：合并
- 发现势力无事件关联 → `delete`：移除

#### 5d. 更新 lore/

- 补充 `history.yaml` 的历史事件与 `first_referenced`
- 补充 `artifacts.yaml` 的物品与 `key_events`
- 补充 `terminology.yaml` 的术语与 `first_appearance`

**只读 `refine_input.json` 统计 + 个别事件**，不读全文。

完成后更新状态：
```yaml
refine_batches:
  current_batch: 6
  batches_completed: 5
  worldbuilding_refined: true
```

### 6. Batch-6：清理汇总

#### 6a. 清理已删除事件的引用

检查所有文件，删除指向不存在事件的引用：
- 人物小传的 `key_events` 中无效 event_id → 删除
- 势力/地点的 `key_events` 中无效 event_id → 删除
- 钩子的 `planted.event` / `harvested.event` 无效 → 删除或标记 pending

#### 6b. 精调 tags.yaml

基于事件标签统计校准小说级标签：
- 主导 event_type 分布 → 校准 `dominant_event_types`
- 主导 emotion 分布 → 校准 `emotional_profile`
- technique 分布 → 校准 `craft_profile`

#### 6c. 更新 SQLite 索引

调用 `build-index` 更新 SQLite 表：
- 更新 `characters` 表的 `appearance_count`、`file_path`
- 更新 `factions` 表
- 更新 `regions` 表
- 新增 `character_events`、`faction_events` 交叉引用表

#### 6d. 标记精调完成

运行脚本更新 refine_hash：
```bash
python scripts/core/extract_refine_data.py {material_id}
```

脚本会自动将新的 `events_hash` 写入 `meta.yaml` 的 `refine_hash` 字段。

更新 `meta.yaml` 其他字段：
```yaml
refine_batches:
  current_batch: 6
  batches_completed: 6
  stats_merged: true
  hooks_verified: true
  characters_refined: true
  relations_verified: true
  worldbuilding_refined: true
  cleanup_done: true

pipeline:
  refined: true
  refined_at: "2026-04-21T12:00:00Z"
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
- **不读原文**：只依赖 event YAML 数据 + refine_input.json 统计
- **备份先行**：修改前备份文件夹结构
- **hash 检测变化**：无变化时跳过，避免重复工作
- **分批执行控制上下文**：每批完成后立即写入，不累积上下文
- **优先读精炼数据**：refine_input.json 约 10-50KB，大幅降低上下文压力
- 事件文件过多时，优先依赖 manifest，必要时分批读取
- 钩子验证采用保守策略：不确定时标 pending，无证据则删除

## References

- [outline.schema.yaml](../../../docs/schemas/outline.schema.yaml)
- [worldbuilding.schema.yaml](../../../docs/schemas/worldbuilding.schema.yaml)
- [characters.schema.yaml](../../../docs/schemas/characters.schema.yaml)
- [novel-tags.schema.yaml](../../../docs/schemas/novel-tags.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)