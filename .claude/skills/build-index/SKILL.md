---
name: build-index
description: 构建事件倒排索引和清单文件，支持高效检索（支持文件夹结构）
when_to_use: 事件拆分完成后，构建索引加速检索
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

为已完成事件拆分的小说构建索引文件，使检索不再需要遍历全部事件文件。

**支持文件夹结构**：characters/、worldbuilding/、outline/ 都采用文件夹结构。

**不读原文，只读 event YAML 数据和其他索引文件。**

**优先使用固化脚本** `scripts/core/build_event_index.py` 和 `scripts/core/build_db.py`，仅在脚本不满足需求时动态补充。

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 events 已完成（或部分完成）
2. 确认 `events/` 目录下有事件文件
3. 检查文件夹结构是否存在：
   - `characters/_index.yaml` + `profiles/`
   - `worldbuilding/_index.yaml` + 各模块
   - `outline/_index.yaml` + 各模块

## 输出文件

### Per-Novel（事件索引）
- `data/novels/{material_id}/events_index.yaml` — 倒排索引（标签 → event_id 列表）
- `data/novels/{material_id}/events_manifest.yaml` — 事件清单（压缩视图）

### Global（跨小说聚合索引）
- `data/character_index.yaml` — 人物索引（从 characters/_index.yaml 聚合）
- `data/plot_index.yaml` — 剧情索引（从 outline/_index.yaml 聚合）

### SQLite（派生查询层）
- `data/material.db` — SQLite 索引库（支持文件夹结构的交叉引用）

遵循对应 schema：
- `docs/schemas/event-unit.schema.yaml` — 事件单元结构
- `docs/schemas/character-index.schema.yaml`
- `docs/schemas/plot-index.schema.yaml`

## 执行步骤

### 0. 运行固化脚本（推荐）

```bash
# 步骤一：构建 YAML 索引（人可读 + git 友好）
python scripts/core/build_event_index.py {material_id}

# 步骤二：构建/更新 SQLite 索引（机器查询加速，支持文件夹结构）
python scripts/core/build_db.py --material {material_id}
```

两个脚本的关系：
- `build_event_index.py` → 生成 YAML 倒排索引和事件清单（**source of truth**）
- `build_db.py` → 将事件 + characters + worldbuilding + hooks 数据导入 SQLite（**派生查询层**）

**`build_db.py` 现支持文件夹结构**：
- 自动读取 `characters/_index.yaml` + `profiles/*.yaml`
- 自动读取 `worldbuilding/factions/` + `geography/`
- 自动读取 `outline/hooks_network.yaml`
- 自动填充交叉引用表 `character_events`、`faction_events`、`region_events`

agent 只需读取脚本输出即可。如果脚本报错或需要特殊处理，再按以下步骤手动执行。

**职责分工**：

| 产出 | 方式 | 说明 |
|------|------|------|
| events_index.yaml | `build_event_index.py` | 脚本完成 |
| events_manifest.yaml | `build_event_index.py` | 脚本完成 |
| material.db (SQLite) | `build_db.py` | 脚本完成（支持文件夹） |
| character_index.yaml | agent 手动 | 需读 characters/_index.yaml |
| plot_index.yaml | agent 手动 | 需读 outline/_index.yaml |

步骤 0 完成 per-novel 索引和 SQLite 后，继续步骤 4-5 聚合全局索引。如果步骤 0 脚本报错，则按步骤 1-3 手动处理 per-novel 部分。

### 1. 遍历事件文件（手动 fallback）

分批读取 `events/` 目录下所有 YAML 文件，每批 50 个。

从每个事件提取：
- `event_id`, `thread`, `chapters`, `title`, `summary`
- 全部标签字段（多层多维）
- `characters`
- `tension_peak`, `tension_curve`
- `plot_function`
- `plot_threads`（如有）
- `hooks`（如有）

### 2. 构建事件清单 (events_manifest.yaml)

每个事件保留检索关键字段，按 event_id 排序：

```yaml
material_id: nm_xxx
total_events: 45
built_at: "2026-04-05T12:00:00Z"

events:
  - id: ev_main_001
    thread: main
    chapters: [1, 2, 3, 4, 5]
    title: "税银案破案自救"
    summary: "许七安穿越入狱，面临流放边陲的命运..."
    event_type: 推理破案
    conflict: [生死, 自由]
    tension_peak: 5
    pacing: 加速
    plot_function: [铺垫, 转折]
    characters: [许七安, 许新年]
    emotion_arc: [恐惧, 挐扎, 狂喜]
```

### 3. 构建倒排索引 (events_index.yaml)

为每个标签维度建立 值 → event_id 列表 的映射：

```yaml
material_id: nm_xxx
total_events: 45
built_at: "2026-04-05T12:00:00Z"

# A. 内容层
event_type:
  推理破案: [ev_main_001, ev_main_005]
  修炼突破: [ev_main_002, ev_subplot_魏渊_001]
conflict:
  生死: [ev_main_001, ev_main_010]
  利益: [ev_main_003, ev_romance_怀庆_002]

# B. 人物层
character:
  许七安: [ev_main_001, ev_main_002, ev_main_003, ...]
  萧容鱼: [ev_main_005, ev_romance_怀庆_001, ...]
thread:
  main: [ev_main_001, ev_main_002, ...]
  romance_怀庆: [ev_romance_怀庆_001, ev_romance_怀庆_002]

# C. 情感层
emotion_arc:
  紧张: [ev_main_005, ev_main_010]
tension_peak:
  5: [ev_main_001, ev_main_015]

# D. 结构层
plot_function:
  铺垫: [ev_main_001, ev_main_003]
  转折: [ev_main_005, ev_main_010]

# E. 技法层
technique:
  闪回: [ev_main_002]

# F. 物理层
setting:
  监牢: [ev_main_001]

# 钩子线索（从 events hooks 字段聚合）
hooks:
  章末悬念: [ev_main_001, ev_main_005]
  道具钩子: [ev_main_002]
```

### 4. 聚合全局人物索引 (character_index.yaml)

**读取文件夹结构** `characters/_index.yaml`，提取每个角色的关键信息，写入 `data/character_index.yaml`。

如果 `character_index.yaml` 已有其他素材的条目，保留它们，只替换当前 material_id 的条目（upsert 语义）。

```yaml
# data/character_index.yaml
entries:
  - material_id: nm_novel_20260405_zhbk
    novel_name: "《书名》"
    characters:
      - name: 许七安
        role: protagonist
        archetype: 英雄
        traits: [果断, 重情义, 隐忍]
        moral_spectrum: 灰色
        arc_summary: "失意商人 → 重生逆袭 → 权力巅峰的孤独"
        arc_stages: 5
        appearance_count: 45        # 出场事件数（从 SQLite 统计）
        first_appearance: "第1章"
        narrative_function: 推动主线
        file_path: characters/profiles/xu_qi_an.yaml  # 小传文件路径
```

**数据来源**：
- 基本信息：`characters/_index.yaml` 的 `roster` 各分类
- 详细信息：如有 `file` 字段，读取 `characters/profiles/{name}.yaml`
- `appearance_count`：从 SQLite 的 `event_characters` 表统计

### 5. 聚合全局剧情索引 (plot_index.yaml)

**读取文件夹结构** `outline/_index.yaml` 和 `events_index.yaml`，提取剧情结构信息，写入 `data/plot_index.yaml`。

同样采用 upsert 语义。

```yaml
# data/plot_index.yaml
entries:
  - material_id: nm_novel_20260405_zhbk
    novel_name: "《书名》"
    genre: [都市, 重生]
    total_events: 45
    structure:
      modules_enabled: [structure, plotlines, hooks_network, pacing_curve]
      acts: 3
      plot_stages:                # 各阶段事件分布
        开篇: 3
        第一幕-诱因: 5
        第一幕-发展: 8
        第二幕-对抗: 12
      hooks_count: 42
      hooks_verified: 38
    dominant_functions:
      - {function: 铺垫, count: 15}
      - {function: 转折, count: 8}
    pacing_profile:
      avg_tension: 3.2
      peak_tension_chapter: 89
```

**数据来源**：
- 基本信息：`outline/_index.yaml`
- 钩子统计：`outline/hooks_network.yaml`（如启用）
- 事件分布：`events_index.yaml`

### 6. 更新 meta.yaml

```yaml
pipeline:
  index_built: true
  index_at: "2026-04-05T12:00:00Z"
  manifest_events: 45
  global_indexes_updated: true
  folder_structure: true  # 标记使用文件夹结构
```

## 增量更新

如果后续新增了事件（continue 模式），`build-index` 支持增量更新：

```bash
# YAML 索引增量更新（需手动处理或重新运行脚本）
python scripts/core/build_event_index.py {material_id}

# SQLite 增量更新
python scripts/core/build_db.py --incremental {material_id}
```

增量更新时：
1. 读取现有 manifest 和 index
2. 扫描 events/ 中不在 manifest 里的新文件
3. 只处理新增部分，合并到现有索引
4. 更新 SQLite 的相关表

## 输出格式

```
✅ 索引构建完成（文件夹结构）

📚 素材：{name}
📊 事件索引：
  事件总数：45
  标签维度：20
  人物索引：{n} 个角色
  钩子线索：{n} 条

📊 SQLite 索引：
  👥 人物：{n} 个（交叉引用：{m} 条）
  🏰 势力：{n} 个（交叉引用：{m} 条）
  🗺️ 地区：{n} 个（交叉引用：{m} 条）
  🪝 钩子：{n} 条

📊 全局索引已更新：
  👥 character_index.yaml — {n} 个角色（本素材）
  📖 plot_index.yaml — {转折点数}/{钩子数}

📄 倒排索引：data/novels/{id}/events_index.yaml
📄 事件清单：data/novels/{id}/events_manifest.yaml
📄 全局人物：data/character_index.yaml
📄 全局剧情：data/plot_index.yaml
📄 SQLite：data/material.db
```

## 注意事项

- **支持文件夹结构**：characters/、worldbuilding/、outline/ 都采用文件夹结构
- 分批读取事件文件（每批 50 个），避免 token 溢出
- 倒排索引中 event_id 列表按事件顺序排列
- manifest 中 summary 截断到 50 字以内
- 索引文件需与实际事件保持一致，新增事件后需重建或增量更新
- `material-search-event` 检索时应优先调用 `scripts/core/search.py` 查 SQLite
- 全局索引采用 upsert 语义——只替换当前 material_id 的条目，保留其他素材数据
- `character_index` 中的 `arc_summary` 应浓缩为一句话，不超过 30 字
- `plot_index` 中的 `turning_points` 只记录主要转折（通常 3-8 个），不穷举
- **SQLite 是 YAML 的派生产物**：如果 `material.db` 丢失或损坏，运行 `python scripts/core/build_db.py` 可从 YAML 完全重建
- **增量更新**：单本小说修改后，用 `python scripts/core/build_db.py --incremental {material_id}` 更新，不必全量重建
- **交叉引用表**：`character_events`、`faction_events`、`region_events` 支持双向检索

## References

- [scripts/core/build_event_index.py](../../../scripts/core/build_event_index.py) — 固化索引脚本
- [scripts/core/build_db.py](../../../scripts/core/build_db.py) — SQLite 构建脚本（支持文件夹）
- [event-unit.schema.yaml](../../../docs/schemas/event-unit.schema.yaml)
- [AGENTS.md](../../../AGENTS.md)