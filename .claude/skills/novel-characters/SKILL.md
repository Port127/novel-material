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

## Schema

输出遵循 `docs/schemas/characters.schema.yaml`。

## 执行步骤

### 1. 提取人物名册

为每个重要角色记录：
- 名字和别名
- 角色定位（protagonist/antagonist/supporting/minor）
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

如果有明确的阵营划分，记录势力、成员和立场。

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
- minor 角色可以省略弧线
