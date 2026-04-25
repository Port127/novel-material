# 全局索引字段

## character_index

建议聚合：

- `material_id`
- `novel_name`
- `characters[]`
  - `name`
  - `role`
  - `archetype`
  - `appearance_count`
  - `first_appearance`
  - `file_path`

## plot_index

建议聚合：

- `material_id`
- `novel_name`
- `total_events`
- `threads`
- `thread_intersections`
- `structure`
- `dominant_functions`
- `pacing_profile`

## 原则

- 示例保持抽象，不写具体作品角色名
- 全局索引是聚合视图，不替代单本素材内部文件
