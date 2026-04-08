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

### 1. 影响评估

在执行前先扫描受影响范围：

1. 读取 `data/tags.yaml`，确认维度、旧值、新值均存在
2. 遍历所有 `data/novels/*/scenes_index.yaml`，统计旧值在倒排索引中关联的 scene_id 数量
3. 遍历所有 `data/novels/*/tags.yaml`，检查小说级标签是否包含旧值

输出影响摘要，等待用户确认后执行。

### 2. 更新标签字典

在 `data/tags.yaml` 中：
- 从维度的 `values` 列表中移除旧值
- 确认新值存在

### 3. 全局替换场景文件

在所有场景文件和小说标签文件中替换：
- `data/novels/*/scenes/*.yaml` — 场景级标签
- `data/novels/*/tags.yaml` — 小说级标签

统计被替换的文件数。

### 4. 重建倒排索引

对每个受影响的小说（即 `scenes_index.yaml` 中包含旧值的小说）：

1. 读取 `scenes_index.yaml`
2. 在对应维度下：将旧值 key 的 scene_id 列表合并到新值 key 下（去重、按章节顺序排列）
3. 删除旧值 key
4. 写回 `scenes_index.yaml`

如果存在固化脚本 `scripts/core/build_scene_index.py`，也可对受影响的 material_id 重跑索引构建。

### 5. 更新场景清单

对受影响的小说，更新 `scenes_manifest.yaml` 中对应场景的标签字段（如果 manifest 包含该维度）。

### 6. 重建 SQLite 索引

YAML 更新后 SQLite 会与 YAML 不一致，必须重建：

```bash
# 对每个受影响的 material_id 重建
python scripts/core/build_db.py --material {material_id}

# 或一次性全量重建
python scripts/core/build_db.py
```

## 输出格式

```
✅ 标签合并完成

📂 维度：{dimension}
🔀 {old_value} → {new_value}
📝 影响统计：
  场景文件：{scene_count} 个
  小说标签：{novel_count} 个
  倒排索引：{index_count} 个已重建
  场景清单：{manifest_count} 个已更新
  SQLite：已重建
```

## 注意事项

- 合并前先评估影响范围，等待用户确认
- 场景文件、倒排索引、场景清单、SQLite 四者必须同步更新，缺一不可
- 合并不可撤销，谨慎操作

## References

- [AGENTS.md](../../../AGENTS.md)
