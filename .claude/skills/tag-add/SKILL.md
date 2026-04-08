---
name: tag-add
description: 向标签字典新增标签值
when_to_use: 场景打标签时发现现有标签值不够用
argument-hint: "[维度] [新值]"
arguments: dimension, value
---

# 任务

向 `data/tags.yaml` 的指定维度新增标签值。

## 前置检查

1. 读取 `data/tags.yaml`
2. 确认维度存在
3. 确认值不重复

## 输入参数

- `$0` (dimension): 标签维度名（如 `scene_type`, `emotion`, `technique`）
- `$1` (value): 新增的标签值

## 执行步骤

### 1. 验证维度

确认 dimension 是 `data/tags.yaml` 中已有的维度。

如果维度不存在，提示用户确认是否要新建维度。

### 2. 检查重复

确认该值不在该维度的 `values` 列表中。

### 3. 追加值

在对应维度的 `values` 列表末尾追加新值。

### 4. 写回

更新 `data/tags.yaml`。

## 输出格式

```
✅ 标签已新增

📂 维度：{dimension}（{description}）
🏷️ 新值：{value}
📊 该维度现有 {count} 个值
```

## 注意事项

- 值应简洁（2-4字为佳）
- 避免同义重复（如"争斗"和"对决"）
- 如有近义值，建议先 `/tag-merge` 确认
- 如新值与现有值容易混淆，同步更新 `docs/TAG_GUIDE.md` 的易混淆对照表
- 新值立即可用于后续场景标签，已入库场景的 SQLite 索引无需重建（标签以值存储，非外键引用）
