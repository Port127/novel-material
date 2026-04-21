---
name: novel-worldbuilding
description: 从小说原文提取世界观设定（文件夹结构：力量体系、地理、势力、背景知识）
when_to_use: 用户想要为入库小说提取世界观和设定信息
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

从小说原文中提取世界观设定体系，生成文件夹结构。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/meta.yaml`
3. 读取 `data/novels/{material_id}/source.txt`
4. 如存在 `chapter_index.yaml`，读取章节行号范围（用于精确定位）
5. 如存在 `outline/_index.yaml`，参考大纲缩小关注范围

## Schema

输出遵循 `docs/schemas/worldbuilding.schema.yaml` 的文件夹结构。

## 上下文控制策略

世界观信息分布不均匀（开篇集中、新地图/新势力揭示时集中）。采用 **outline 导航 + 定向采样 + 补扫** 策略：

| 小说规模 | 策略 |
|----------|------|
| ≤ 50 章 | 一次性读取全文 |
| 51-300 章 | outline 导航 + 定向读取关键段落 + 尾部补扫 |
| > 300 章 | 同上，但分 2-3 轮采样，每轮聚焦不同维度 |

## 执行步骤

### 1. 制定阅读计划

#### 1a. 有 outline 时（推荐路径）

从 `outline/_index.yaml` 和 `outline/structure.yaml` 识别世界观密集区域：
- 各幕开篇章节（通常引入新设定）
- 标注为「转折点」的章节（可能涉及力量升级、势力变动）
- 情节线索涉及探秘/修炼/战争的章节段

生成**采样清单**：需要精读的章节范围列表（通常占全书 30-50%）。

#### 1b. 无 outline 时

分段扫描，策略同 `novel-outline` 的分段方案，但每段侧重提取设定信息。

### 2. 分段读取 + 提取

按采样清单分批读取原文，每批控制在 context window 安全范围内。

#### 2a. 力量体系

识别小说中的力量/修炼/科技体系：
- 体系名称和类型
- 等级划分（从低到高）
- 核心运作规则
- 限制条件和代价
- 特殊能力/技能（主要的）

如果小说无明确力量体系（如纯都市文），此项标记 `has_power_system: false`。

#### 2b. 地理空间

提取重要地点和空间结构：
- 空间层级关系
- 每个重要地区的描述、子地点、连通关系
- 地点在剧情中的重要性

**统计地区数量，决定粒度**：
- ≤ 3 个地区 → 单文件 `geography.yaml`
- > 3 个或存在层级 → 文件夹 `geography/`

#### 2c. 势力组织

从世界观角度梳理各势力：
- 组织类型、势力范围、实力等级
- 关键人物（领袖、核心成员）
- 势力间关系

**统计势力数量，决定粒度**：
- ≤ 3 个势力 → 单文件 `factions.yaml`
- > 3 个或关系复杂 → 文件夹 `factions/`

此处关注「势力本身的设定」，与 `characters/_index.yaml` 的 `factions_summary`（关注「谁属于哪个阵营」）互补。

#### 2d. 背景知识

提取背景设定：
- **历史事件**：影响当前剧情的重大历史
- **种族/物种**：非人种族或特殊物种
- **重要道具/神器**：关键物品的名称、描述、持有者
- **专有名词**：小说独创的术语及含义

写入 `lore/` 文件夹的各子模块。

### 3. 汇总合成

合并所有提取结果，整理层级关系。

#### 3a. 创建文件夹结构

创建 `data/novels/{material_id}/worldbuilding/`：

```
worldbuilding/
├── _index.yaml              # 概览 + 模块索引 + 统计
├── power_system.yaml        # 力量体系
├── geography.yaml           # 简单时（≤3 地区）
├── geography/               # 复杂时（>3 地区）
│   ├── _index.yaml
│   └── {region_name}.yaml
├── factions.yaml            # 简单时（≤3 势力）
├── factions/                # 复杂时（>3 势力）
│   ├── _index.yaml
│   └── {faction_name}.yaml
└── lore/
    ├── history.yaml
    ├── artifacts.yaml
    ├── species.yaml
    └── terminology.yaml
```

#### 3b. 处理冲突

如果后续批次发现与前批冲突（如力量等级描述前后不一致），以更晚出现的描述为准并标注。

### 4. 建立交叉引用（初步）

为每个势力、地点标注：
- `key_events`：关联事件（如已知，填入 event_id；未知留空待 refine 补充）
- `associated_factions` / `associated_locations`：关联势力/地点

**注意**：完整的交叉引用在 refine 阶段补充，本阶段只做初步标注。

### 5. 更新状态

将 `meta.yaml` 中 `status` 更新为 `worldbuilt`（如果当前是 `outlined`）。

## 输出格式

```
✅ 世界观设定已生成（文件夹结构）

📚 素材：{name}
📁 目录：data/novels/{id}/worldbuilding/

⚡ 力量体系：{体系名称}（{等级数}级）/ 无
🗺️ 地理：{N}个地区 → {单文件/文件夹}
🏰 势力：{M}个组织 → {单文件/文件夹}
📜 lore：历史/{H}条 | 物品/{A}条 | 种族/{S}个 | 术语/{T}个

模块索引（写入 _index.yaml）：
  complexity: {high/medium/low}

后续步骤：
  /novel-characters {id}    # 生成人物体系
```

## 注意事项

- 世界观采用文件夹结构，粒度自适应（≤3 单文件，>3 文件夹）
- `_index.yaml` 存概览和统计，不替代 SQLite
- 力量体系关注规则和等级，不需列出每个角色实力
- 地理只记录对剧情有影响的地点
- 势力与 `characters/_index.yaml` 的 `factions_summary` 互补而非重复
- 术语只记录读者需要理解的核心名词
- 短篇（≤50 章）可一次性读取
- 段落笔记只保留提取结果，不摘抄原文
- 交叉引用在 refine 阶段补充详细验证

## References

- [worldbuilding.schema.yaml](../../../docs/schemas/worldbuilding.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)