---
name: novel-tags
description: 为小说生成整体多维标签
when_to_use: 用户想要为入库小说打整体标签
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

为小说生成整体级别的多维标签，描述全书的类型、基调、叙事风格和参考价值。

**小说级标签与事件级标签不同**：事件标签描述单个事件（6 层 20 维），小说标签描述全书特征（7 维），值域在 `data/tags.yaml` 的 G 部分（genre / tone / narrative_structure / time_handling / prose_style / writing_strength / tropes）。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/meta.yaml`
3. 读取 `data/tags.yaml` — 获取 G 部分（小说级标签）的合法值
4. 读取 `docs/schemas/novel-tags.schema.yaml` — 获取输出格式

优先读取已有分析产出物（避免重读原文）：
- `outline.yaml` — 结构、节奏、时间线信息 → 用于 narrative / tone
- `worldbuilding.yaml` — 世界观复杂度 → 用于 genre / tropes
- `characters.yaml` — 人物体系 → 用于 tropes / writing_strength

## Schema

输出遵循 `docs/schemas/novel-tags.schema.yaml`。

## 上下文控制策略

小说级标签是全书层面的判断，**不需要**逐章精读。采用 **已有产出优先 + 抽样验证** 策略：

| 条件 | 策略 |
|------|------|
| outline + worldbuilding + characters 均存在 | 只读这三个产出物 + 抽样 2-3 章原文验证风格判断 |
| 仅有 outline | 读 outline + 抽样 5 章原文（开头 2 章 + 中段 2 章 + 高潮 1 章） |
| 无任何产出物 | 抽样读 8-10 章原文（均匀分布 + 开头/高潮/结尾） |

**抽样章节选取**：
- 开头 1-2 章：判断叙事视角、语言风格
- 中段章节（~40% 位置）：验证节奏和基调稳定性
- 高潮章节（从 outline 的 turning_point 定位）：判断情感强度和基调上限
- 结尾章节：判断收束风格

## 执行步骤

### 1. 采集信息

按上下文控制策略，收集以下判断依据：

| 维度 | 信息来源 | 判断依据 |
|------|---------|---------|
| genre / sub_genre | outline.premise + worldbuilding | 世界观类型、核心设定 |
| theme | outline.theme + 钩子网络 | 反复出现的核心议题 |
| tone | 抽样章节 + outline.pacing | 全书主导情绪氛围 |
| narrative.structure | outline.structure + timelines | 有几条叙事线 |
| narrative.pov_style | 抽样章节 | 叙事视角 |
| narrative.time_handling | outline.timelines | 时间线是否非线性 |
| style.prose | 抽样章节 | 遣词造句的风格 |
| style.strength | outline + characters + worldbuilding | 哪方面写得最好 |
| tropes | outline + characters 的模式 | 套路识别 |
| good_for | 综合判断 | 对写作者有什么参考价值 |

### 2. 逐维度标注

#### 2a. genre / sub_genre（类型）

从 `data/tags.yaml` → `genre` 维度选取。

- `genre`：1-2 个主类型（如 `[都市, 重生]`）
- `sub_genre`：2-4 个子类型，更细粒度（如 `[商战, 情感, 创业]`），可用自由文本

判断原则：以世界观和核心冲突为主要依据，不以标签热度为依据。

#### 2b. theme（主题）

3-5 个核心主题，用短语表达。从 outline 的 premise/theme 字段提取，结合钩子网络中反复出现的议题。

#### 2c. tone（基调）

从 `data/tags.yaml` → `tone` 维度选取，2-3 个值。

**判断依据**：
- 读抽样章节的叙述语气、对话风格、事件氛围
- 参考 outline 的 pacing_note 描述
- 注意：tone 是**全书主基调**，不是某几章的情绪。一本热血为主、偶尔沉重的小说，tone 应该是 `[热血]` 而非 `[热血, 沉重]`

#### 2d. narrative（叙事特征）

- `structure`：从 `data/tags.yaml` → `narrative_structure` 选取（单线/双线/多线/环形/碎片化）
- `pov_style`：从原文判断（第一人称/第三人称限制/全知/多视角轮转）——此字段为自由文本
- `time_handling`：从 `data/tags.yaml` → `time_handling` 选取

#### 2e. style（写作风格）

- `prose`：从 `data/tags.yaml` → `prose_style` 选取，1-2 个值
- `strength`：从 `data/tags.yaml` → `writing_strength` 选取，2-4 个值
- `weakness`：可留空 `[]`，如有明显短板可标注

**判断 prose 的方法**：读 2-3 段抽样原文，看句子长度、修辞密度、情感表达方式。
**判断 strength 的方法**：综合 outline（结构设计能力）、characters（人物塑造能力）、worldbuilding（世界观设计能力）、抽样原文（对话/节奏/氛围能力）。

#### 2f. tropes（套路识别）

从 `data/tags.yaml` → `tropes` 维度选取，2-5 个值。

识别方法：
- 从 outline 的 premise 和 structure 判断核心套路（如 "重生 + 利用未来记忆" → `满级重生`）
- 从 characters 的人物设定判断（如 "扮猪吃虎" → `扮猪吃虎`）
- 从 worldbuilding 判断（如 "系统面板" → `系统流`）
- 只标注**突出使用**的套路，不要因为沾边就标

#### 2g. good_for（参考价值）

4-8 条自然语言描述，说明这部小说**对写作者有什么参考价值**。每条应具体指向一个可检索的方向。

好的 good_for：
- "都市重生文参考，重生后利用未来记忆创业的经典套路"
- "毒舌主角的性格塑造，对话风格独特"
- "双子主角的情感羁绊写作"

差的 good_for：
- "好看"（太空泛）
- "小说写得不错"（无检索价值）

### 3. 写入 tags.yaml

写入 `data/novels/{material_id}/tags.yaml`，格式遵循 schema：

```yaml
material_id: {id}

genre: [都市, 重生]
sub_genre: [商战, 情感, 创业]
theme: [重生逆袭, 创业致富, 情感抉择]
tone: [热血, 温情]

narrative:
  structure: 单线
  pov_style: 第三人称限制
  time_handling: 线性

style:
  prose: [口语化]
  strength: [人物塑造, 对话, 节奏控制]
  weakness: []

tropes: [满级重生, 小人物崛起]

good_for:
  - "都市重生文参考，利用未来记忆创业的完整路径"
  - "双女主修罗场处理参考"
  - "商战创业线参考"
```

### 4. 质量自检

写入后检查：

| 检查项 | 标准 |
|--------|------|
| genre 值合法 | 所有值在 `data/tags.yaml` → genre 维度内 |
| tone 值合法 | 所有值在 `data/tags.yaml` → tone 维度内 |
| prose 值合法 | 所有值在 `data/tags.yaml` → prose_style 维度内 |
| strength 值合法 | 所有值在 `data/tags.yaml` → writing_strength 维度内 |
| tropes 值合法 | 所有值在 `data/tags.yaml` → tropes 维度内 |
| narrative.structure 合法 | 在 narrative_structure 维度内 |
| narrative.time_handling 合法 | 在 time_handling 维度内 |
| good_for 非空 | 至少 3 条，每条有具体参考方向 |
| theme 非空 | 至少 2 个 |

如有不合法值，替换为最近义的合法值，或调用 `/tag-add` 新增。

### 5. 更新状态

将 `meta.yaml` 中 `status` 更新为 `tagged`（如果当前是 `outlined`）。

## 输出格式

```
✅ 小说标签已生成

📚 素材：{name}
🏷️ 类型：{genre} / {sub_genre}
🎭 基调：{tone}
📖 叙事：{structure} / {pov_style} / {time_handling}
✍️ 风格：{prose} | 长板：{strength}
🎯 套路：{tropes}
💡 参考价值：{good_for 第一条}

📁 文件：data/novels/{id}/tags.yaml

后续步骤：
  /pipeline-scenes {id}    # 拆分全书事件
```

## 注意事项

- 标签值必须从 `data/tags.yaml` G 部分（小说级维度）中选取
- 如果需要新标签值，先调用 `/tag-add` 添加到字典
- good_for 字段用自然语言描述，是检索时的关键匹配信号
- 小说标签是全书宏观特征，不要被个别章节的风格偏差误导
- 优先利用已有产出物（outline/worldbuilding/characters），减少重读原文

## References

- [novel-tags.schema.yaml](../../../docs/schemas/novel-tags.schema.yaml)
- [data/tags.yaml](../../../data/tags.yaml) — G 部分为小说级维度
- [AGENTS.md](../../../AGENTS.md)
