---
name: build-index
description: 根据事件与文件夹结构产物构建 per-novel 索引、全局聚合索引和 SQLite 查询层
---

# 任务

为已拆分事件的素材构建索引层，支持高效检索。

## 边界

用于：
- 构建 `events_manifest.yaml`
- 构建 `events_index.yaml`
- 更新 `data/material.db`
- 聚合 `character_index.yaml` 与 `plot_index.yaml`

不用于：
- 读取原文
- 替代事件拆分

## 输入

- `material_id`

## 默认执行路径

### 1. 前置检查

- `events/` 非空
- `outline/`、`characters/`、`worldbuilding/` 的相关索引存在

### 2. 优先跑固化脚本

默认执行：

```bash
python scripts/core/build_event_index.py {material_id}
python scripts/core/build_db.py --material {material_id}
```

职责：

- `build_event_index.py`：per-novel YAML 索引
- `build_db.py`：SQLite 查询层

### 3. 聚合全局索引

基于文件夹结构提取当前素材的：

- 人物聚合条目
- 剧情聚合条目

写入：

- `data/character_index.yaml`
- `data/plot_index.yaml`

采用 upsert 语义，只替换当前 `material_id`。

### 4. 手动 fallback

只有脚本报错时，才手动：

- 遍历事件文件
- 汇总 manifest
- 建倒排索引
- 再补全全局聚合

### 5. 更新状态

完成后写：

- `pipeline.index_built = true`
- `pipeline.index_at`

## 输出要求

至少输出：

- 事件总数
- manifest / index 是否生成
- SQLite 是否更新
- 全局索引是否 upsert 成功

## 关键硬约束

- 不读原文
- SQLite 是 YAML 的派生层
- 全局索引必须 upsert，不覆盖其他素材
- 优先脚本，不优先手工

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/global-index-fields.md`
- `../../../scripts/core/build_event_index.py`
- `../../../scripts/core/build_db.py`
- `../../../docs/schemas/event-unit.schema.yaml`
- `../../../docs/schemas/character-index.schema.yaml`
- `../../../docs/schemas/plot-index.schema.yaml`
- `../../../AGENTS.md`
