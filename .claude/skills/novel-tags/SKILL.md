---
name: novel-tags
description: 为小说生成整体多维标签
when_to_use: 用户想要为入库小说打整体标签
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

为小说生成整体级别的多维标签。

## 前置检查

1. 读取 `data/index.yaml`，确认 material_id 存在
2. 读取 `data/novels/{material_id}/source.txt`（或参考已有的 outline/characters）
3. 读取 `data/tags.yaml` 获取合法标签值

## Schema

输出遵循 `docs/schemas/novel-tags.schema.yaml`。

## 执行步骤

### 1. 分析全书特征

从以下维度分析（标签值从 `data/tags.yaml` G 部分选取）：

- **genre / sub_genre**：类型
- **theme**：主题
- **tone**：基调
- **narrative**：叙事结构、视角、时间处理
- **style**：文笔风格、写作长板
- **tropes**：叙事套路/常见模式（从 `data/tags.yaml` 的 `tropes` 维度选取）
- **good_for**：适合参考的方向

### 2. 写入 tags.yaml

写入 `data/novels/{material_id}/tags.yaml`。

### 3. 更新状态

将 `meta.yaml` 中 `status` 更新为 `tagged`（如果当前是 `outlined`）。

## 输出格式

```
✅ 小说标签已生成

📚 素材：{name}
🏷️ 类型：{genre}
🎭 基调：{tone}
📁 文件：data/novels/{id}/tags.yaml
```

## 注意事项

- 标签值必须从 `data/tags.yaml` 字典中选取
- 如果需要新标签，先调用 `/tag-add` 添加到字典
- good_for 字段用自然语言描述，指导检索时的匹配
