---
name: material-delete
description: 删除素材及其所有关联资源。破坏性操作，不可恢复。当用户明确要求删除指定 material_id 时使用。
---

# material-delete

删除素材及其所有关联资源。**破坏性操作，不可恢复。**

## 前置条件

- 已确认用户明确要求删除指定素材
- 已确认 `material_id` 存在于 `data/novels/` 目录中

## 执行命令

```bash
python scripts/utils/material_delete.py <material_id>
```

## 清理范围

该脚本会删除以下全部内容：

1. **本地文件**：`data/novels/{material_id}/` 整个目录（含 source.txt、所有 YAML、outline、characters、worldbuilding、chapters、向量文件）
2. **数据库记录**：`novels`、`chapters`、`characters`、`character_appearances`、`outline_sequences`、`outline_beats`、`worldbuilding_entities` 表中与该 `material_id` 关联的所有行
3. **全局索引**：从 `data/index.yaml` 中移除该条目

## 成功校验

1. `data/novels/{material_id}/` 目录不再存在
2. `data/index.yaml` 中不再包含该 `material_id`

## 安全规则

- MUST 在执行前向用户确认："即将删除素材 {material_id}（{name}），此操作不可恢复，确认？"
- NEVER 在用户未明确确认的情况下执行删除
- NEVER 批量删除多个素材，每次只删一个