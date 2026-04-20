---
name: refine
description: 场景完成后精调 outline / characters / tags，建立钩子网络和精确弧线
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
- 所有 `plot_threads`（如有）→ 按 thread_id 聚类
- 每个场景的 `characters[].name` → 人物出场统计
- 每个场景的 `character_moment` → 人物转变节点
- 每个场景的 `relationship` + `interaction` → 关系演变数据

**钩子数据采集（钩子系统统一采集）**：

| 来源 | 字段 | 说明 |
|------|------|------|
| 事件 hooks 字段 | `hooks.chapter_end` | 章末悬念（悬念铆合） |
| 事件 hooks 字段 | `hooks.items_crossing` | 跨事件道具（因果铆合） |
| 事件 hooks 字段 | `hooks.character_crossing` | 人物关联（反转铆合） |
| 事件 hooks 字段 | `hooks.info_hint` | 信息钩子疑似 |
| 场景 plot_function | `伏笔埋设` | 反转铆合埋设点 |
| 场景 plot_function | `伏笔回收` | 反转铆合回收点 |

**融合策略**：
- `plot_function: 伏笔埋设` → 自动标注 `crossing_type: 反转铆合`，提取埋设信息
- `plot_function: 伏笔回收` → 自动标注 `crossing_type: 反转铆合`，提取回收信息
- 两种来源的钩子统一验证，统一写入 `hooks_network`

**注意：场景数量可能很大（数百甚至上千），优先读取 `scenes_manifest.yaml` 或 `scenes_index.yaml`。如需读取原始 scene 文件，分批进行。**

### 2. 钩子验证与铆合链建立

精调阶段建立完整的钩子铆合链（含反转铆合、因果铆合、悬念铆合等）。

#### 2a. 钩子数据合并

将两个来源的钩子数据合并：

**来源一：事件 hooks 字段**
- 已有行号引用、置信度标注
- 已标注钩子类型（道具/人物/信息/悬念）

**来源二：plot_function 反转铆合**
- 提取场景中 `plot_function: [伏笔埋设]` 的埋设点（反转铆合）
- 提取场景中 `plot_function: [伏笔回收]` 的回收点（反转铆合）
- 自动标注 `crossing_type: 反转铆合`
- 根据场景内容推断 `hook_type`（道具/人物/信息/情感）

**合并规则**：
- 同一钩子在两个来源都有记录 → 优先使用 hooks 字段（有行号）
- plot_function 反转铆合补充铆合形式 → 自动标注"反转铆合"
- plot_function 反转铆合推断钩子类型 → 根据埋设内容推断

#### 2b. 埋设-回收匹配

对合并后的钩子执行埋设-回收匹配：

**匹配流程**：

```
Step 1: 识别所有埋设点
  - hooks 字段的 planted 位置
  - plot_function: 伏笔埋设 的场景
  
Step 2: 识别所有回收点
  - hooks 字段的 harvested 位置（已知时）
  - plot_function: 伏笔回收 的场景
  
Step 3: 匹配埋设和回收
  - 同一 hook_type + 同一元素（道具名/人物名/信息关键词）
  - 建立铆合链（埋设 → 回收）
  
Step 4: 标注铆合形式
  - plot_function 反转铆合 → crossing_type: 反转铆合
  - hooks 字段道具 → crossing_type: 因果铆合 或 反转铆合（根据内容）
  - hooks 字段悬念 → crossing_type: 悬念铆合
```

**匹配示例**：

```yaml
# plot_function 反转铆合匹配
埋设点（plot_function: 伏笔埋设）:
  - scene: ch03_s02
  - content: "师傅用左手喝茶"
  
回收点（plot_function: 伏笔回收）:
  - scene: ch50_s01
  - content: "师傅的右手是义肢"
  
匹配结果:
  - hook_type: 情感钩子
  - crossing_type: 反转铆合           # 自动标注
  - planted: {event: ev_main_001, chapter: 3}
  - harvested: {event: ev_main_005, chapter: 50}
```

#### 2c. 置信度验证与调整

对已匹配的钩子验证置信度：

**置信度调整规则**：

|| 原置信度 | 验证结果 | 新置信度 |
||----------|----------|----------|
|| high | 已验证回收 | high（保持） |
|| high | 未找到回收 | medium（降级） + 标记"待回收" |
|| medium | 已验证回收 | high（升级） |
|| medium | 未找到回收 | low（降级） + 标记"待回收" |
|| low | 已验证回收 | medium（升级） |
|| low | 未找到回收 | 删除（无证据支撑） |

**plot_function 反转铆合置信度**：
- 有明确埋设-回收匹配 → confidence: high
- 只有埋设无回收 → confidence: medium + 标记"待回收"
- 埋设内容模糊难推断 → confidence: low

#### 2d. 隐性钩子识别

精调阶段补充事件拆解时遗漏的隐性钩子：

**人物钩子识别**：
- 扫描同一人物在不同事件的身份/立场变化
- 检查人物出场时的微妙描写是否在后续事件揭示原因
- 自动标注 `crossing_type: 反转铆合`

**信息钩子识别**：
- 扫描对话和背景描写中的细节
- 检查是否在后续事件成为关键推理依据
- 置信度默认 low，需明确文本证据才能升级

**情感钩子识别**：
- 扫描角色的微妙反应（表情复杂、沉默、异样眼神）
- 检查是否在后续事件揭示原因
- 需要明确文本证据，否则删除

#### 2e. 钩子铆合链汇总

建立全局钩子铆合链，写入 `outline.yaml` 的 `hooks_network` 字段：

```yaml
hooks_network:
  # 铆合链列表（埋设→回收）
  chains:
    - hook_id: hook_001
      hook_type: 道具钩子
      crossing_type: 因果铆合           # 因果关联
      planted:
        event: ev_main_001
        chapter: 3
        item: 神秘石头
        description: 主角在市集买的石头
        source: hooks                    # 来源：hooks 字段
      harvested:
        event: ev_main_005
        chapter: 50
        description: 石头是封印神兽的钥匙
      confidence: high
      
    - hook_id: hook_002
      hook_type: 人物钩子
      crossing_type: 反转铆合           # 认知反转
      planted:
        event: ev_main_001
        chapter: 5
        character: 热心路人
        description: 出场时眼神有微妙异样
        source: plot_function            # 来源：plot_function 反转铆合
      harvested:
        event: ev_main_005
        chapter: 80
        description: 热心路人其实是反派卧底
      confidence: high
      
  # 待回收钩子（未找到回收事件的钩子）
  pending:
    - hook_id: hook_003
      hook_type: 信息钩子
      crossing_type: 反转铆合
      planted_event: ev_main_002
      planted_chapter: 12
      detail: '城东的井水最近变苦了'
      confidence: low
      note: 需后续章节验证
      
  # 统计数据
  stats:
    total_hooks: 45
    verified_hooks: 38
    pending_hooks: 7
    by_type:
      道具钩子: 15
      人物钩子: 12
      悬念钩子: 8
      信息钩子: 6
      情感钩子: 4
    by_crossing:
      反转铆合: 15                      # 认知反转钩子
      因果铆合: 20
      悬念铆合: 8
      期待铆合: 7
    by_source:
      hooks_field: 30                   # 来自事件 hooks 字段
      plot_function: 15                 # 来自 plot_function 反转铆合
```

**迁移原有 foreshadowing 字段**：
- 如果 `outline.yaml` 已有 `foreshadowing` 字段
- 迁移到 `hooks_network.chains`，标注 `crossing_type: 反转铆合`
- 删除原有 `foreshadowing` 字段

#### 2f. 更新事件文件的 hooks 字段

对验证后的钩子，更新对应事件文件的 `hooks` 字段：
- 填充 `resolved_in` 或 `expected_harvest`
- 更新 `confidence`
- 添加 `crossing_type`（铆合形式）
- 添加 `source` 标记

### 3. 精调 outline.yaml

#### 3a. 钩子网络写入

将钩子验证阶段建立的铆合链写入 `outline.yaml` 的 `hooks_network` 字段（见第 2e 节）。

#### 3b. 节奏曲线补充

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

#### 3c. 转折点校准

从 `plot_function: [转折/反转]` 的场景提取实际转折点，与 outline 的 `turning_point` 对比校准。

### 4. 精调 characters.yaml

#### 4a. 人物弧线细化

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

#### 4b. 关系演变时间线

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

#### 4c. 出场频率标注

为每个角色补充 `appearance_count` 和 `active_chapters` 范围。

#### 4d. 心理深度补充

基于场景中的 `character_moment`（道德抉择、信念崩塌/重建、堕落滑落等）和具体行为推断，为主要角色补充 `psychology` 维度中缺失的字段：

- `fatal_flaw`: 从道德抉择失误、反复犯错的模式中提取
- `obsession`: 从角色持续追求的目标中提取
- `soft_spot`: 从守护/牺牲行为的对象中提取
- `misbelief`: 从信念崩塌/重建事件的触发信念中提取
- `contrast_habit`: 从日常场景中与角色身份反差的细节中提取
- `tragedy_trigger`: 从导致角色错过/误判的结构性事件模式中提取

只补充有场景证据支撑的字段，无信号时留空。标记 `source: refine`。

### 5. 精调 worldbuilding.yaml（如存在）

基于场景数据补充世界观信息：
- 从场景的 `setting` 标签统计高频地点 → 补充 `geography.regions`
- 从场景中出现的势力/组织信息 → 校准 `factions_world` 的关系和实力
- 从角色能力描写 → 补充 `power_system` 的等级和能力细节
- 新增的信息标记 `source: refine`

### 6. 精调 tags.yaml（小说级）

基于场景标签的统计分布，补充或校准小说级标签：
- 主导 scene_type 分布 → 校准小说的 `dominant_scene_types`
- 主导 emotion 分布 → 校准 `emotional_profile`
- technique 分布 → 校准 `craft_profile`

### 7. 标记精调完成

在 `meta.yaml` 中记录精调状态：

```yaml
pipeline:
  refined: true
  refined_at: "2026-04-05T12:00:00Z"
  refine_summary:
    hooks_verified: 38
    hooks_pending: 7
    hooks_from_plot_function: 15       # 来自 plot_function 反转铆合
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
  🪝 钩子网络建立
    - 验证钩子：{n} 个（已回收）
    - 待回收钩子：{n} 个（未找到回收事件）
    - 铆合链建立：{n} 条
    - 来源分布：hooks字段 {n}个，plot_function反转铆合 {n}个
    - 钩子网络：已写入 outline.yaml

  📖 outline.yaml
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
- 钩子系统统一处理：`plot_function: 伏笔埋设/回收` 自动标注 `crossing_type: 反转铆合`
- 原有 `foreshadowing` 字段迁移到 `hooks_network.chains`，标注来源
- 钩子验证采用保守策略：不确定时标 `confidence: low`，标记为"待回收"
- 钩子验证时优先确认跨事件关系，同一事件内的钩子不算跨事件钩子
- 待回收钩子需标注并记录，方便后续验证或人工审核

## References

- [outline.schema.yaml](../../../docs/schemas/outline.schema.yaml)
- [worldbuilding.schema.yaml](../../../docs/schemas/worldbuilding.schema.yaml)
- [characters.schema.yaml](../../../docs/schemas/characters.schema.yaml)
- [novel-tags.schema.yaml](../../../docs/schemas/novel-tags.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)