---
name: material-delete
description: 删除素材及其所有关联资源（文件夹、索引、数据库记录）
when_to_use: 用户想要删除一个素材，需要彻底清理所有关联数据
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

删除素材及其所有关联资源，确保无残留。

## 输入参数

- `$0` (material_id): 要删除的素材 ID，格式如 `nm_novel_20260405_zhbk`

## 素材关联资源

一个素材在系统中存在以下层级的数据：

| 层级 | 文件/数据 | 内容 |
|------|----------|------|
| L3 全局索引 | `data/index.yaml` | 素材路由记录 |
| L3 全局索引 | `data/plot_index.yaml` | 事件聚合（由 build-index 生成） |
| L3 全局索引 | `data/character_index.yaml` | 人物聚合（由 build-index 生成） |
| L4 SQLite | `data/material.db` | novels/events/event_tags/event_characters/characters 表 |
| L5 文件夹 | `{folder}` | 素材文件夹（路径由 index.yaml 的 folder 字段指定） |

## 执行步骤

### 1. 验证素材 ID

从 `data/index.yaml` 查找素材记录，获取其 `folder` 字段：

```bash
grep "{material_id}" data/index.yaml
```

如果素材不存在于 index.yaml，报错退出：

```
❌ 素材不存在

ID：{material_id}
请检查 ID 是否正确，或使用 /material-search 查找现有素材。
```

如果素材存在，提取其 `folder` 字段值作为实际文件夹路径（可能为 `data/novels/{id}/` 或 `novels/{id}/` 等非标准路径）。

### 2. 一致性检查

在删除前，检查三层数据是否一致：

```bash
# 检查文件夹是否存在
ls -la {folder}/

# 检查 SQLite 记录
sqlite3 data/material.db "SELECT COUNT(*) FROM novels WHERE material_id='{material_id}';"
```

输出一致性状态：

| 层级 | 状态 | 说明 |
|------|------|------|
| index.yaml | 存在/不存在 | 路由记录 |
| 文件夹 | 存在/不存在 | {folder} |
| SQLite novels | 存在/不存在 | novels 表记录 |

**不一致处理**：
- 如果文件夹已不存在但 index.yaml 有记录 → 提示"将清理 index.yaml 残留记录"
- 如果 SQLite 有记录但文件夹不存在 → 提示"将清理 SQLite 残留记录"
- 如果文件夹存在但 index.yaml 无记录 → 提示"异常状态，文件夹未被索引"

### 3. 收集删除信息

统计该素材关联的所有资源：

```bash
# 文件夹大小和文件数（如文件夹存在）
du -sh {folder}/
find {folder} -type f | wc -l

# SQLite 记录数（如果 DB 存在）
sqlite3 data/material.db "
  SELECT 'novels', COUNT(*) FROM novels WHERE material_id='{material_id}';
  SELECT 'events', COUNT(*) FROM events WHERE material_id='{material_id}';
  SELECT 'event_tags', COUNT(*) FROM event_tags WHERE material_id='{material_id}';
  SELECT 'characters', COUNT(*) FROM characters WHERE material_id='{material_id}';
  SELECT 'event_characters', COUNT(*) FROM event_characters WHERE material_id='{material_id}';
"
```

同时读取 `{folder}/meta.yaml` 获取素材名称、作者、状态（如文件夹存在）。

### 4. 预览删除内容

```
🗑️ 素材删除预览

📚 ID：{material_id}
📄 名称：{name}
👤 作者：{author}
📋 状态：{status}

数据一致性状态：
- index.yaml：存在 ✓ / 不存在 ❌
- 文件夹 {folder}：存在 ✓ / 不存在 ❌
- SQLite novels：存在 ✓ / 不存在 ❌

将要删除的资源：

┌─ 文件夹 ──────────────────────────────────────
│  {folder}/
│  大小：{size}MB
│  文件：{file_count} 个
│    - meta.yaml（元数据）
│    - source.txt（原文）
│    - outline/（大纲文件夹）
│    - worldbuilding/（世界观文件夹）
│    - characters/（人物文件夹）
│    - tags.yaml（标签）
│    - events/*.yaml（{event_count} 个事件）
│    - events_index.yaml（倒排索引）
│    - events_manifest.yaml（事件清单）
│    - stats.yaml/md/html（统计报告）
│    - ...（其他文件）
└──────────────────────────────────────────────

┌─ SQLite 数据库 ───────────────────────────────
│  novels 表：{novel_count} 条
│  events 表：{event_count} 条
│  event_tags 表：{tag_count} 条
│  characters 表：{char_count} 条
│  event_characters 表：{ec_count} 条
└──────────────────────────────────────────────

┌─ 全局索引 ────────────────────────────────────
│  data/index.yaml：移除路由记录
│  data/plot_index.yaml：重建（移除该素材事件）
│  data/character_index.yaml：重建（移除该素材人物）
└──────────────────────────────────────────────

⚠️ 此操作不可撤销，删除后数据将永久丢失。

确认删除？(yes/no)
```

### 5. 检查 Pipeline 状态提醒

如果素材状态为以下值，给出特别提醒：

| 状态 | 提醒 |
|------|------|
| `processing` | ⚠️ 该素材正在处理中，删除将丢失未完成的进度 |
| `events` | ⚠️ 事件拆分进行中，删除将丢失已拆分的部分事件 |
| `complete` / `refined` | 正常删除，无特别提醒 |

### 6. 用户确认

等待用户输入 `yes` 或 `no`：

- `yes` → 继续执行删除
- `no` → 取消操作，退出

### 7. 执行删除

用户确认后，按顺序执行：

#### 7.1 删除 SQLite 数据

```bash
sqlite3 data/material.db "
  DELETE FROM event_characters WHERE material_id='{material_id}';
  DELETE FROM event_tags WHERE material_id='{material_id}';
  DELETE FROM events WHERE material_id='{material_id}';
  DELETE FROM characters WHERE material_id='{material_id}';
  DELETE FROM novels WHERE material_id='{material_id}';
  VACUUM;
"
```

> 注意：`VACUUM` 用于清理删除后的数据库空间。

#### 7.2 更新 index.yaml

读取 `data/index.yaml`，从 `materials` 列表中移除该素材的记录，写入文件。

#### 7.3 删除文件夹

```bash
rm -rf {folder}/
```

#### 7.4 重建全局聚合索引

运行 `build-index` 对所有剩余素材重建聚合索引：

```bash
python scripts/core/build_event_index.py --rebuild-all
```

或逐个读取剩余素材的 events 和 characters 文件，更新聚合索引。

### 8. 验证残留清理

执行删除后，必须验证各层数据已彻底清理：

```bash
# 验证 index.yaml 无残留
grep "{material_id}" data/index.yaml && echo "❌ 残留" || echo "✓ 已清理"

# 验证文件夹无残留
ls -la {folder}/ 2>/dev/null && echo "❌ 残留" || echo "✓ 已清理"

# 验证 SQLite 无残留
sqlite3 data/material.db "
  SELECT 'novels', COUNT(*) FROM novels WHERE material_id='{material_id}';
  SELECT 'events', COUNT(*) FROM events WHERE material_id='{material_id}';
  SELECT 'event_tags', COUNT(*) FROM event_tags WHERE material_id='{material_id}';
  SELECT 'characters', COUNT(*) FROM characters WHERE material_id='{material_id}';
  SELECT 'event_characters', COUNT(*) FROM event_characters WHERE material_id='{material_id}';
"
```

所有结果必须为 0 或"已清理"，否则报告异常。

### 9. 记录删除日志

在 `data/deletion_log.yaml` 中追加记录（如文件不存在则创建）：

```yaml
- material_id: {id}
  name: {name}
  author: {author}
  status: {status}
  deleted_at: {timestamp}
  deleted_by: material-delete skill
  stats:
    event_count: {event_count}
    file_count: {file_count}
    tag_count: {tag_count}
    character_count: {char_count}
  consistency_note: {不一致情况说明，如有}
```

### 10. 输出报告

```
✅ 素材已删除

📚 ID：{material_id}
📄 名称：{name}

已删除资源：
  - 文件夹 {folder}/ ({file_count} 个文件)
  - SQLite 记录 ({event_count} 事件, {tag_count} 标签, {char_count} 人物)
  - index.yaml 路由记录
  - 全局聚合索引已重建

残留验证：
  ✓ index.yaml 无残留
  ✓ 文件夹无残留
  ✓ SQLite 各表无残留

删除日志已记录到 data/deletion_log.yaml

剩余素材：{remaining_count} 部
```

## 硬约束

- MUST 先预览再删除，展示所有关联资源
- MUST 等待用户明确输入 `yes` 确认后才执行删除
- MUST 检查素材状态，对处理中的素材给出特别提醒
- MUST 同步清理三层数据（文件夹 + SQLite + 索引文件）
- MUST 记录删除日志到 `data/deletion_log.yaml`
- MUST 删除后重建全局聚合索引（plot_index/character_index）
- MUST 删除后验证残留已彻底清理
- MUST 使用 index.yaml 中的 folder 字段作为实际文件夹路径
- MUST 执行 SQLite VACUUM 清理空间
- NEVER 批量删除多个素材（每次只删除一个）
- NEVER 软删除或保留任何残留文件
- NEVER 删除 `data/tags.yaml`（标签字典是全局共享的）
- NEVER 在素材不存在时静默失败（必须报错提示）

## 注意事项

- 删除操作不可撤销，建议用户确认前仔细核对
- 删除后可通过重新 `/material-add` 或 `/material-import` 恢复素材（需重新处理）
- 如果 SQLite 不存在（`data/material.db`），跳过数据库清理步骤
- 如果素材文件夹已不存在但 index.yaml 有残留记录，仍需清理索引
- 如果三层数据不一致，在预览阶段明确标注，并在删除日志中记录

## References

- [material-add/SKILL.md](../material-add/SKILL.md)
- [material-import/SKILL.md](../material-import/SKILL.md)
- [build-index/SKILL.md](../build-index/SKILL.md)
- [ARCHITECTURE.md](../../../ARCHITECTURE.md)
- [AGENTS.md](../../../AGENTS.md)