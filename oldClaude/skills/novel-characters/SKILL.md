---
name: novel-characters
description: 从小说原文提取人物名册、关系网和人物弧线（文件夹结构：索引 + 人物小传）
when_to_use: 用户想要为入库小说生成人物体系
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

从小说原文中提取人物体系，生成文件夹结构。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/meta.yaml`
3. 读取 `data/novels/{material_id}/source.txt`
4. 如存在 `chapter_index.yaml`，读取章节行号范围
5. 如存在 `outline/_index.yaml`，参考大纲识别人物密集区域
6. 如存在 `worldbuilding/_index.yaml`，参考势力组织和力量体系

## Schema

输出遵循 `docs/schemas/characters.schema.yaml` 的文件夹结构。

## 上下文预算

| 操作 | 最大读取量 | 说明 |
|------|-----------|------|
| 扫描章节标题 | 不限 | 只读标题行，不读正文 |
| 单章阅读 | 单章全文 | 用于事件拆分/精调 |
| 批量阅读 | ≤ 5 章/次 | 用于 outline 分段阅读 |
| 补录阅读 | ≤ 3 章/次 | 只读遗漏实体相关章节 |

**禁止**：
- 一次性读取 > 10 章正文
- 在不分段的情况下读取全文
- 将上一步的完整输出原样传递到下一步

## 上下文控制策略

人物信息随剧情逐渐展开——角色陆续登场、关系不断演变、弧线贯穿全书。采用 **outline 导航 + 分段扫描 + 滚动积累** 策略：

| 小说规模 | 策略 |
|----------|------|
| ≤ 50 章 | 一次性读取全文 |
| 51-300 章 | 分 3-5 段，每段积累人物信息后传递给下一段 |
| > 300 章 | 分 5-10 段，每段只传递压缩版人物名册 |

**关键区别**：与 outline/worldbuilding 不同，人物提取需要**跨段传递**已发现的角色名单，以便识别关系演变和弧线转折。

## 执行步骤

### 1. 制定阅读计划

#### 1a. 有 outline 时（推荐路径）

从 `outline/_index.yaml` 和 `outline/structure.yaml` 识别人物密集区域：
- 各幕开篇（新角色集中登场）
- 转折点章节（角色弧线关键节点）
- 高冲突章节（关系变化、阵营重组）

结合结构信息划定分段范围，段边界优先对齐幕/卷分界。

#### 1b. 无 outline 时

等距分段，策略同 `novel-outline` 的分段方案。

### 2. 分段扫描 + 滚动积累

对每一段：

#### 2a. 读取本段原文

按章节索引定位，同时携带**滚动名册摘要**：
- 已发现角色的名字 + 身份 + 最新状态
- 不携带完整弧线细节

#### 2b. 提取本段人物信息

- **新角色**：首次出场的角色，记录名字、别名、身份、首次出场章节
- **弧线节点**：已知角色在本段的状态变化（转变事件 + 章节号）
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

将当前段笔记合并到**滚动名册**（用于传递给下一段）：
```
滚动名册（传递用）：
- {name}: {role}, 首现第{N}章, 当前状态: {state}
- {name}: {role}, 首现第{N}章, 当前状态: {state}
...
```

滚动名册不含弧线细节和关系描述，只保留最小信息。

### 3. 汇总合成

所有段落笔记收集完毕后，综合生成人物体系。

#### 3a. 编制角色名册

按角色类型分类：
- **protagonist**：主要角色，必须有详细小传
- **antagonist**：反派角色，必须有详细小传
- **supporting**：重要配角，有弧线者生成小传
- **minor**：龙套角色，只在 `_index.yaml` 保留基本信息

为每个角色记录：
- 名字和别名
- 角色定位（从 `data/tags.yaml` archetype 选取）
- 叙事功能（从 `data/tags.yaml` narrative_function 选取）
- 首次出场章节
- 核心特征一句话
- 性格特征标签
- 道德光谱

#### 3b. 绘制人物弧线

为主要角色（protagonist + antagonist + 有弧线的 supporting）生成完整弧线：
- 起点 → 转变 → 终点
- 每阶段状态描述
- 触发转变的事件
- 对应章节

#### 3c. 构建关系网

合并各段关系变化：
- 关系类型（从 `data/tags.yaml` relationship 选取）
- 关系描述
- 关系演变轨迹（如有）

#### 3d. 标注阵营

如有势力划分，记录：
- 势力名称和成员
- 领袖
- 立场描述

与 `worldbuilding/factions/` 的势力设定保持一致（此处关注「谁属于」，worldbuilding 关注「势力本身」）。

### 4. 创建文件夹结构

创建 `data/novels/{material_id}/characters/`：

```
characters/
├── _index.yaml              # 名册索引 + 关系概览 + 统计
├── relations.yaml           # 关系网详情
└── profiles/                # 人物小传（主角/重要配角）
    ├── {name_pinyin}.yaml
    └── ...
```

#### 4a. 写入 _index.yaml

- 全部角色名册（按 protagonist/antagonist/supporting/minor 分类）
- 关系概览（核心关系）
- 阵营概览
- 统计数据

#### 4b. 写入 relations.yaml

- 关系列表详情
- 关系演变轨迹
- 网络图数据（可选）

#### 4c. 写入人物小传

为 protagonist/antagonist 和有弧线的 supporting 生成 `profiles/{name_pinyin}.yaml`：
- 基本信息
- 心理深度维度
- 人物弧线
- 关系网络
- **key_events**（初步，待 refine 补充）
- 对白样本（可选）
- 阵营归属

**⚠️ API 速率限制约束（硬约束）**：

为防止触发 API Key Rate Limit，文件写入必须遵守以下限制：

| 规则 | 说明 |
|------|------|
| **单次消息最多 2 个 Write 调用** | 一次响应中最多并行写入 2 个文件 |
| **每个人物小传独立写入** | 写完一个文件后，确认完成再写下一个 |
| **禁止批量重写** | 不得在单条消息中重写 3 个以上已存在文件 |

**执行策略**：先写 `_index.yaml` + `relations.yaml`（同一消息）→ 然后逐个写人物小传（每次最多 2 个）。

**注意**：minor 角色不生成小传文件，只在 `_index.yaml` 的 `minor` 列表中保留基本信息。

### 5. 建立交叉引用（初步）

在人物小传中标注：
- `key_events`：关联事件（如已知填入 event_id，否则留空）
- `worldbuilding_links`：关联势力/地点

**完整交叉引用在 refine 阶段补充**。

### 6. 更新状态

将 `meta.yaml` 中 `status` 更新为 `characterized`（如果当前是 `worldbuilt`）。

## 输出格式

```
✅ 人物体系已生成（文件夹结构）

📚 素材：{name}
📁 目录：data/novels/{id}/characters/

👥 人物：{N}个
  - 主角：{x}个 → profiles/{name}.yaml ✓
  - 反派：{y}个 → profiles/{name}.yaml ✓
  - 配角：{z}个 → profiles/{m}个 + 索引{n}个
  - 龙套：{w}个 → 仅索引

🔗 关系：{M}条 → relations.yaml
📊 阵营：{K}个 → _index.yaml + worldbuilding/factions/

文件列表：
  - _index.yaml（名册索引）
  - relations.yaml（关系网）
  - profiles/{name}.yaml（人物小传）

后续步骤：
  /novel-tags {id}          # 生成小说级标签
  /novel-events {id} 1-5    # 拆分事件
```

## 注意事项

- 人物采用文件夹结构：主角/重要配角有小传，龙套只索引
- `_index.yaml` 存全部角色一览，龙套无 file 字段
- 心理深度维度（fatal_flaw 等）对主角/反派必填，配角可选
- 弧线只记录主要角色，minor 角色可省略
- 关系类型必须从 `data/tags.yaml` relationship 维度选取
- 角色原型必须从 `data/tags.yaml` archetype 维度选取
- key_events 只记录关键节点（≤10 个），避免膨胀
- 短篇（≤50 章）可一次性读取
- 滚动名册是跨段传递的唯一载体，保持精简
- 交叉引用在 refine 阶段补充完整

## References

- [characters.schema.yaml](../../../docs/schemas/characters.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)