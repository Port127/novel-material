# material-delete 删除清单

## 删除前必须确认

- `data/index.yaml`
- 素材目录
- `data/material.db`
- 全局聚合索引

## 删除后必须验证

- `index.yaml` 无该 `material_id`
- 目录不存在
- SQLite 记录为 0
- 聚合索引已重建

## 输出时必须说清楚

- 实际删除了什么
- 有没有发现历史残留
- 残留是否已清理
