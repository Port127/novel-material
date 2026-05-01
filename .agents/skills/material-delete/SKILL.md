# material-delete

删除素材及其所有关联资源。

## 用法

```bash
python scripts/utils/delete.py <material_id>
```

## 清理范围

- 小说目录 (`data/novels/{material_id}/`)
- 数据库记录（novels, chapters, characters, worldbuilding, outline）
- 全局索引 (`data/index.yaml`)

## 注意

这是破坏性操作，执行前需要确认。
