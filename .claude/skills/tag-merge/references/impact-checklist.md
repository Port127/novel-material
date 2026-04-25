# tag-merge 影响评估

## 评估范围

- `data/tags.yaml`
- `data/novels/*/events/*.yaml`
- `data/novels/*/tags.yaml`
- `events_manifest.yaml`
- `events_index.yaml`
- SQLite

## 执行后要验证

- 旧值已清空
- 新值替换完整
- 索引与数据库一致
