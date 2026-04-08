---
name: refine
description: 场景完成后精调 outline / characters / tags，补充伏笔网络和精确弧线
when_to_use: 所有场景拆分完成后，用场景数据反哺精调早期产出物
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

在所有 scenes 完成后，利用场景级标签数据精调 `outline.yaml`、`worldbuilding.yaml`、`characters.yaml`、`tags.yaml`。

**不读原文，只读 scene YAML 数据。**

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 status 为 `complete` 或 `tagged`
2. 确认 `scenes/` 目录下有场景文件
3. 确认 `outline.yaml`、`characters.yaml`、`tags.yaml` 均已存在
4. 如存在 `worldbuilding.yaml`，一并纳入精调

如果存在 `scenes_manifest.yaml`，优先读取 manifest 而非逐个读 scene 文件。

## 执行步骤

### 0. 备份待修改文件

精调会覆盖写入多个关键文件，在修改前为每个文件创建 `.bak` 备份：

```bash
cp outline.yaml outline.yaml.bak
cp characters.yaml characters.yaml.bak
cp tags.yaml tags.yaml.bak
cp worldbuilding.yaml worldbuilding.yaml.bak   # 如存在
```

备份文件仅保留最近一次（覆盖旧 `.bak`）。如果精调结果有问题，可从 `.bak` 恢复。

### 1. 采集场景数据

从所有 scene YAML 中提取：
- 每个场景的 `tension` 值 → 按章聚合
- 所有 `plot_function` 含 `伏笔埋设` / `伏笔回收` 的场景
- 所有 `plot_threads`（如有）→ 按 thread_id 聚类
- 每个场景的 `characters[].name` → 人物出场统计
- 每个场景的 `character_moment` → 人物转变节点
- 每个场景的 `relationship` + `interaction` → 关系演变数据

**注意：场景数量可能很大（数百甚至上千），优先读取 `scenes_manifest.yaml` 或 `scenes_index.yaml`。如需读取原始 scene 文件，分批进行。**

### 2. 精调 outline.yaml

#### 2a. 伏笔网络补充

从场景中提取所有伏笔埋设/回收点，与 outline 现有 `foreshadowing` 对比：
- 新发现的伏笔 → 追加到 `foreshadowing` 列表
- 已有伏笔缺少 payoff_chapter → 从场景数据补充
- 标注置信度：`confidence: high/medium/low`

```yaml
foreshadowing:
  - id: f001
    plant_chapter: 3
    plant_scene: ch03_s02
    plant_description: "伏笔描述"
    payoff_chapter: 800
    payoff_scene: ch800_s01
    payoff_description: "回收描述"
    confidence: high
    source: refine        # 标记来源
```

#### 2b. 节奏曲线补充

用场景 tension 均值填充 `pacing_curve`，生成逐章（或每10章）粒度的节奏数据：

```yaml
pacing_curve:
  - chapter: 1
    tension: 2.0
    note: "日常切入"
  - chapter: 2
    tension: 2.5
  # ...每章一个数据点
```

#### 2c. 转折点校准

从 `plot_function: [转折/反转]` 的场景提取实际转折点，与 outline 的 `turning_point` 对比校准。

### 3. 精调 characters.yaml

#### 3a. 人物弧线细化

用 `character_moment` 标签丰富每个角色的 `arc`：

```yaml
arc:
  - stage: "起点"
    state: "重生归来的成功商人"
    chapter: 1
    scene: ch01_s01
    moment_type: 性格展示
  - stage: "转变"
    state: "第一次面对情感两难"
    trigger: "萧容鱼告白"
    chapter: 156
    scene: ch156_s03
    moment_type: 道德抉择
```

#### 3b. 关系演变时间线

从 `relationship` + `interaction` 随章节变化的数据，为 `relations[].evolution` 补充更细粒度的阶段：

```yaml
evolution:
  - stage: "初遇"
    state: "陌生人"
    chapter: 3
    scene: ch03_s01
    interaction: 试探
  - stage: "暧昧"
    state: "互有好感"
    chapter: 45
    scene: ch45_s02
    interaction: 合作
```

#### 3c. 出场频率标注

为每个角色补充 `appearance_count` 和 `active_chapters` 范围。

#### 3d. 心理深度补充

基于场景中的 `character_moment`（道德抉择、信念崩塌/重建、堕落滑落等）和具体行为推断，为主要角色补充 `psychology` 维度中缺失的字段：

- `fatal_flaw`: 从道德抉择失误、反复犯错的模式中提取
- `obsession`: 从角色持续追求的目标中提取
- `soft_spot`: 从守护/牺牲行为的对象中提取
- `misbelief`: 从信念崩塌/重建事件的触发信念中提取
- `contrast_habit`: 从日常场景中与角色身份反差的细节中提取
- `tragedy_trigger`: 从导致角色错过/误判的结构性事件模式中提取

只补充有场景证据支撑的字段，无信号时留空。标记 `source: refine`。

### 4. 精调 worldbuilding.yaml（如存在）

基于场景数据补充世界观信息：
- 从场景的 `setting` 标签统计高频地点 → 补充 `geography.regions`
- 从场景中出现的势力/组织信息 → 校准 `factions_world` 的关系和实力
- 从角色能力描写 → 补充 `power_system` 的等级和能力细节
- 新增的信息标记 `source: refine`

### 5. 精调 tags.yaml（小说级）

基于场景标签的统计分布，补充或校准小说级标签：
- 主导 scene_type 分布 → 校准小说的 `dominant_scene_types`
- 主导 emotion 分布 → 校准 `emotional_profile`
- technique 分布 → 校准 `craft_profile`

### 6. 标记精调完成

在 `meta.yaml` 中记录精调状态：

```yaml
pipeline:
  refined: true
  refined_at: "2026-04-05T12:00:00Z"
  refine_summary:
    foreshadowing_added: 15
    pacing_points_added: 1070
    character_arcs_enriched: 8
    relations_enriched: 12
    worldbuilding_enriched: true
```

## 输出格式

```
✅ 精调完成

📚 素材：{name}

精调结果：
  📖 outline.yaml
    - 伏笔：新增 {n} 条（总计 {total}）
    - 节奏曲线：补充 {n} 个数据点
    - 转折点：校准 {n} 处

  👥 characters.yaml
    - 弧线细化：{n} 个角色
    - 关系演变：{n} 条关系链
    - 出场统计：已标注

  🗺️ worldbuilding.yaml
    - 地理补充：{n} 个地点
    - 势力校准：{n} 处

  🏷️ tags.yaml
    - 标签校准：{n} 个维度

后续操作：
  /novel-stats {id}       # 生成统计报告
  /build-index {id}       # 构建检索索引
```

## 注意事项

- 精调是增量操作，不删除已有内容，只追加/修正
- 新增的字段标记 `source: refine` 区分来源
- 不读原文，只依赖 scene YAML 数据
- 场景文件过多时，优先依赖 manifest/index，必要时分批读取
- 伏笔关联采用保守策略，不确定时标 `confidence: low`

## References

- [outline.schema.yaml](../../../docs/schemas/outline.schema.yaml)
- [worldbuilding.schema.yaml](../../../docs/schemas/worldbuilding.schema.yaml)
- [characters.schema.yaml](../../../docs/schemas/characters.schema.yaml)
- [novel-tags.schema.yaml](../../../docs/schemas/novel-tags.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)
