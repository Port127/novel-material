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
2. 读取 `data/novels/{material_id}/source.txt`
3. 如存在 `outline.yaml`，优先参考大纲中的结构信息
4. 如存在 `worldbuilding.yaml`，参考其中势力组织和力量体系信息

## Schema

输出遵循 `docs/schemas/characters.schema.yaml`。

## 执行步骤

### 1. 提取人物名册

为每个重要角色记录：
- 名字和别名
- 角色定位（protagonist/antagonist/supporting/minor）
- 角色原型（从 `data/tags.yaml` 的 `archetype` 维度选取：英雄/导师/门槛守卫/信使/变形者/影子/盟友/骗术师/逗乐者/小人物）
- 叙事功能（从 `data/tags.yaml` 的 `narrative_function` 维度选取：推动主线/提供信息/制造冲突/缓解气氛/主题承载/镜像对照/情感锚点/工具人/世界观展示）
- 首次出场章节
- 核心特征描述（一句话）
- 性格特征标签
- 道德光谱

### 2. 绘制人物弧线

为主要角色记录弧线（起点→转变→终点）：
- 每个阶段的状态描述
- 触发转变的事件
- 对应章节

### 3. 构建关系网

记录主要人物关系：
- 关系类型（从 `data/tags.yaml` 的 `relationship` 维度选取）
- 关系描述
- 关系演变轨迹（可选）

### 4. 标注阵营/势力

如果有明确的阵营划分，记录：
- 势力名称和成员
- 领袖
- 立场描述
- 内部层级结构
- 对立势力

如存在 `worldbuilding.yaml`，参考其中 `factions_world` 的信息保持一致。此处关注「谁属于哪个阵营」，worldbuilding 关注「阵营本身的设定」。

### 5. 写入 characters.yaml

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
  /novel-scenes {id} 1-5    # 拆分场景
```

## 注意事项

- 只记录对剧情有影响的角色，不需要穷举所有出场人物
- 弧线只记录主要角色（protagonist + antagonist + 重要 supporting）
- 关系类型必须从 `data/tags.yaml` 的 `relationship` 维度选取
- 角色原型必须从 `data/tags.yaml` 的 `archetype` 维度选取
- 叙事功能必须从 `data/tags.yaml` 的 `narrative_function` 维度选取
- minor 角色可以省略弧线、原型和叙事功能
