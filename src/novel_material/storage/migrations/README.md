# 数据库迁移说明

## 执行顺序
迁移脚本按编号顺序执行：
1. `001_add_key_event.sql` - 添加 key_event 和 key_plot_point 字段

## 使用方式

### 已有数据库执行迁移
```bash
# 方法 1：手动执行
docker exec -it novel-material-pg psql -U admin -d novel_material -f /path/to/migration.sql

# 方法 2：通过 psql 连接执行
psql $DATABASE_URL < src/novel_material/storage/migrations/001_add_key_event.sql
```

### 新数据库初始化
新数据库无需执行迁移，直接执行 schema.sql 即可：
```bash
make db-init  # 或 nm storage init-db
```

## 迁移历史
- 001_add_key_event.sql (2025-05-09): 添加章节关键事件字段