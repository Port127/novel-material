---
name: novel-characters
description: 从小说中提取人物名册、关系网和人物弧线
when_to_use: 用户想要为入库小说生成人物体系
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

从小说原文中提取人物体系。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 确认 `data/novels/{material_id}/source.txt` 存在
3. 如存在 `chapter_index.yaml`，读取章节行号范围（用于步骤 2 精确定位原文段落）
4. 如存在 `outline.yaml`，优先参考大纲中的结构信息
5. 如存在 `worldbuilding.yaml`，参考其中势力组织和力量体系信息

## Schema

输出遵循 `docs/schemas/characters.schema.yaml`。

## 上下文控制策略

人物信息随剧情逐渐展开——角色陆续登场、关系不断演变、弧线贯穿全书。采用 **outline 导航 + 分段扫描 + 滚动积累** 策略：

| 小说规模 | 策略 |
|----------|------|
| ≤ 50 章 | 一次性读取全文 |
| 51-300 章 | 分 3-5 段，每段积累人物信息后传递给下一段 |
| > 300 章 | 分 5-10 段，每段只传递压缩版人物名册给下一段 |

**关键区别**：与 outline/worldbuilding 不同，人物提取需要**跨段传递**已发现的角色名单，以便后续段落能识别关系演变和弧线转折。

## 执行步骤

### 1. 制定阅读计划

#### 有 outline.yaml 时（推荐路径）

从 `outline.yaml` 中识别人物密集区域：
- 各幕开篇（新角色集中登场）
- 转折点章节（角色弧线关键节点）
- 高冲突章节（关系变化、阵营重组）

结合结构信息划定分段范围，段边界优先对齐幕/卷分界。

#### 无 outline.yaml 时

等距分段，策略同 `novel-outline` 的分段方案。

### 2. 分段扫描 + 滚动积累

对每一段：

#### 2a. 读取本段原文

按章节索引定位，只读当前段的章节文本。同时携带**前序段落传递的人物名册摘要**（仅名字 + 身份 + 最新状态，不携带完整弧线细节）。

#### 2b. 提取本段人物信息

- **新角色**：首次出场的角色，记录名字、别名、身份、首次出场章节
- **弧线节点**：已知角色在本段发生的状态变化（转变事件 + 章节号）
- **新关系**：本段建立或变化的角色关系
- **阵营变动**：角色加入/离开势力

产出**段落笔记**：

```
段落 {N}（第 {start}-{end} 章）
新增角色：[{name, role, first_chapter}]
弧线节点：[{character, event, chapter, state_change}]
关系变化：[{from, to, type, chapter}]
阵营变动：[{character, faction, action, chapter}]
```

#### 2c. 压缩并传递

将当前段笔记合并到**滚动人物名册**中，用于传递给下一段：

```
滚动名册（传递用，仅含关键信息）：
- {name}: {role}, 首现第{N}章, 当前状态: {state}
- {name}: {role}, 首现第{N}章, 当前状态: {state}
...
```

**滚动名册不含弧线细节和关系描述**，只保留足够识别角色身份的最小信息，控制 context 累积。

### 3. 汇总合成

所有段落笔记收集完毕后，综合生成完整人物体系：

#### 3a. 编制人物名册

为每个重要角色记录：
- 名字和别名
- 角色定位（protagonist/antagonist/supporting/minor）
- 角色原型（从 `data/tags.yaml` 的 `archetype` 维度选取）
- 叙事功能（从 `data/tags.yaml` 的 `narrative_function` 维度选取）
- 首次出场章节
- 核心特征描述（一句话）
- 性格特征标签
- 道德光谱
- **心理深度维度**（主要角色必填，配角可选，minor 省略）：
  - `fatal_flaw`: 会害到自己或他人的关键缺陷
  - `obsession`: 长期追求、放不下的事物
  - `soft_spot`: 最在意的人或事
  - `misbelief`: 坚信但并不完全正确的信念
  - `contrast_habit`: 与身份或表象相反的小习惯
  - `tragedy_trigger`: 容易触发错过/误判/等待落空的结构点

#### 3b. 绘制人物弧线

从各段的弧线节点合并，为主要角色生成完整弧线（起点→转变→终点）：
- 每个阶段的状态描述
- 触发转变的事件
- 对应章节

#### 3c. 构建关系网

从各段的关系变化合并，记录主要人物关系：
- 关系类型（从 `data/tags.yaml` 的 `relationship` 维度选取）
- 关系描述
- 关系演变轨迹（可选）

#### 3d. 标注阵营/势力

如果有明确的阵营划分，记录：
- 势力名称和成员
- 领袖
- 立场描述
- 内部层级结构
- 对立势力

如存在 `worldbuilding.yaml`，参考其中 `factions_world` 的信息保持一致。此处关注「谁属于哪个阵营」，worldbuilding 关注「阵营本身的设定」。

### 4. 写入 characters.yaml

写入 `data/novels/{material_id}/characters.yaml`。

## 输出格式

```
✅ 人物体系已生成

📚 素材：{name}
👥 人物：{N}个（主角{x} 配角{y} 龙套{z}）
🔗 关系：{M}条
📁 文件：data/novels/{id}/characters.yaml

后续步骤：
  /novel-tags {id}          # 生成小说级标签
  /novel-events {id} 1-5    # 拆分事件
```

## 注意事项

- 只记录对剧情有影响的角色，不需要穷举所有出场人物
- 弧线只记录主要角色（protagonist + antagonist + 重要 supporting）
- 关系类型必须从 `data/tags.yaml` 的 `relationship` 维度选取
- 角色原型必须从 `data/tags.yaml` 的 `archetype` 维度选取
- 叙事功能必须从 `data/tags.yaml` 的 `narrative_function` 维度选取
- minor 角色可以省略弧线、原型和叙事功能
- 短篇（≤50 章）可一次性读取，无需分段
- 滚动名册是跨段传递的唯一载体，必须保持精简（每角色一行）

## References

- [characters.schema.yaml](../../../docs/schemas/characters.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)
