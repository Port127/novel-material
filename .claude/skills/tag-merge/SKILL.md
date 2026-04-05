---
name: tag-merge
description: 合并同义标签值，保持标签体系一致性
when_to_use: 发现标签值重复或同义，需要统一
argument-hint: "[维度] [旧值] [新值]"
arguments: dimension, old_value, new_value
---

# 任务

在指定维度中将旧值合并为新值，并更新所有引用。

## 前置检查

1. 读取 `data/tags.yaml`
2. 确认维度和两个值存在且不同

## 执行步骤

### 1. 更新标签字典

在 `data/tags.yaml` 中：
- 从维度的 `values` 列表中移除旧值
- 确认新值存在

### 2. 全局替换

在所有场景文件和小说标签文件中替换：
- `data/novels/*/scenes/*.yaml` — 场景级标签
- `data/novels/*/tags.yaml` — 小说级标签

### 3. 统计变更

记录被替换的文件数。

## 输出格式

```
✅ 标签合并完成

📂 维度：{dimension}
🔀 {old_value} → {new_value}
📝 影响文件：{count}个
```

## 注意事项

- 合并前建议先搜索确认旧值的使用范围
- 合并不可撤销，谨慎操作
