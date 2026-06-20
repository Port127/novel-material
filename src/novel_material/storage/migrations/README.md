# 数据库迁移说明

此目录保存**已有数据库**升级时需要按顺序执行的 SQL。全新数据库无需手动执行这些文件，直接运行：

```bash
nm storage init-db
```

## 执行顺序

1. `001_add_key_event.sql`：为章节补充关键事件和结构角色字段。
2. `002_add_chapter_tags.sql`：为章节补充情感、场景、叙事技巧和钩子等标签字段。

已有数据库升级时，应按编号顺序执行尚未应用的迁移，例如：

```bash
psql -d novel_material -f src/novel_material/storage/migrations/001_add_key_event.sql
psql -d novel_material -f src/novel_material/storage/migrations/002_add_chapter_tags.sql
```

执行前请先备份数据库。迁移文件应保持幂等，重复执行不应破坏已有数据。

## 历史记录

| 版本 | 文件 | 说明 |
|---|---|---|
| 001 | `001_add_key_event.sql` | 新增章节关键事件和结构角色字段 |
| 002 | `002_add_chapter_tags.sql` | 新增章节级标签字段 |
