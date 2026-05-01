# pipeline-finalize

收尾流水线：精调 + 同步数据库。

## 用法

```bash
python scripts/core/sync_db.py <material_id>
```

## 流程

1. 校验所有 YAML 文件的完整性
2. 计算 embedding 向量
3. 同步到 PostgreSQL（novels/chapters/outline/characters/worldbuilding）
4. 更新 meta.yaml 状态为 `indexed`

## 输出状态

- meta.yaml 中 `status: indexed`
