---
name: novel-worldbuilding
description: 从小说中提取世界观设定（力量体系、地理空间、势力组织、背景知识）
when_to_use: 用户想要为入库小说提取世界观和设定信息
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

从小说原文中提取世界观设定体系。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/source.txt`
3. 如存在 `outline.yaml`，参考大纲中的结构信息缩小关注范围

## Schema

输出遵循 `docs/schemas/worldbuilding.schema.yaml`。

## 执行步骤

### 1. 提取力量体系

识别小说中的力量/修炼/科技体系：
- 体系名称和类型
- 等级划分（从低到高）
- 核心运作规则
- 限制条件和代价
- 特殊能力/技能（主要的）

如果小说无明确力量体系（如纯都市文），此项留空或标注"无"。

### 2. 构建地理空间

提取小说中出现的重要地点和空间结构：
- 空间层级关系（如：大陆→国家→城市→区域）
- 每个重要地区的描述、子地点、连通关系
- 地点在剧情中的重要性

重点关注反复出场或承载关键剧情的地点，不需穷举所有提及的地名。

### 3. 梳理势力组织

从世界观角度梳理各势力/组织：
- 组织类型、势力范围、实力等级
- 关键人物（领袖、核心成员）
- 势力间的关系（敌对/同盟/从属/竞争）

注意：此处关注「势力本身的设定」，与 `characters.yaml` 中 `factions`（关注「谁属于哪个阵营」）互补。

### 4. 整理背景知识

提取小说世界的背景设定：
- **历史事件**：影响当前剧情的重大历史（附影响说明）
- **文化要素**：风俗、信仰、社会结构
- **种族/物种**：非人种族或特殊物种
- **重要道具/神器**：关键物品的名称、描述、持有者
- **专有名词**：小说独创的术语及含义

### 5. 归纳世界规则

提取小说世界的运作规则：
- 自然法则（如：灵气潮汐规律）
- 社会规则（如：宗门等级制度）
- 禁忌/限制（如：不可逆天改命）

### 6. 写入 worldbuilding.yaml

写入 `data/novels/{material_id}/worldbuilding.yaml`。

## 输出格式

```
✅ 世界观设定已生成

📚 素材：{name}
⚡ 力量体系：{体系名称}（{等级数}级）
🗺️ 地理区域：{N}个
🏰 势力组织：{M}个
📜 专有名词：{K}个
📁 文件：data/novels/{id}/worldbuilding.yaml

后续步骤：
  /novel-characters {id}    # 生成人物体系
```

## 注意事项

- 世界观提取是全书层面的概览，不需要逐章细节
- 力量体系关注规则和等级，不需列出每个角色的具体实力
- 地理只记录对剧情有影响的地点
- 势力组织与 `characters.yaml` 的 `factions` 互补而非重复
- 专有名词只记录读者需要理解的核心术语
- 长篇小说可结合 outline 聚焦关键段落

## References

- [worldbuilding.schema.yaml](../../../docs/schemas/worldbuilding.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
