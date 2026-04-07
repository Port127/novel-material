---
name: build-index
description: 构建场景倒排索引和清单文件，支持高效检索
when_to_use: 场景拆分完成后，构建索引加速检索
argument-hint: "[material_id]"
arguments: material_id
---

# 任务

为已完成场景拆分的小说构建两个索引文件：倒排索引（`scenes_index.yaml`）和场景清单（`scenes_manifest.yaml`），使检索不再需要遍历全部场景文件。

**不读原文，只读 scene YAML 数据。**

**优先使用固化脚本** `scripts/build_scene_index.py`，仅在脚本不满足需求时动态补充。

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 scenes 已完成（或部分完成）
2. 确认 `scenes/` 目录下有场景文件

## 输出文件

### Per-Novel（场景索引）
- `data/novels/{material_id}/scenes_index.yaml` — 倒排索引（标签 → scene_id 列表）
- `data/novels/{material_id}/scenes_manifest.yaml` — 场景清单（压缩视图）

### Global（跨小说聚合索引）
- `data/character_index.yaml` — 人物索引（跨小说人物汇总）
- `data/plot_index.yaml` — 剧情索引（跨小说剧情结构汇总）

遵循对应 schema：
- `docs/schemas/scenes-index.schema.yaml`
- `docs/schemas/scenes-manifest.schema.yaml`
- `docs/schemas/character-index.schema.yaml`
- `docs/schemas/plot-index.schema.yaml`

## 执行步骤

### 0. 运行固化脚本（推荐）

```bash
# 步骤一：构建 YAML 索引（人可读 + git 友好）
python scripts/build_scene_index.py {material_id}

# 步骤二：构建/更新 SQLite 索引（机器查询加速）
python scripts/build_db.py --material {material_id}
```

两个脚本的关系：
- `build_scene_index.py` → 生成 YAML 倒排索引和场景清单（**source of truth**）
- `build_db.py` → 将场景数据导入 SQLite（**派生查询层**，可随时重建）

agent 只需读取脚本输出即可。如果脚本报错或需要特殊处理，再按以下步骤手动执行。

### 1. 遍历场景文件

分批读取 `scenes/` 目录下所有 YAML 文件，每批 50 个。

从每个场景提取：
- `scene_id`, `chapter`, `title`, `summary`
- 全部标签字段（6 层 22 维）
- `characters[].name`
- `tension`
- `plot_function`
- `plot_threads`（如有）

### 2. 构建场景清单 (scenes_manifest.yaml)

每个场景保留检索关键字段，按 scene_id 排序：

```yaml
material_id: nm_xxx
total_scenes: 907
built_at: "2026-04-05T12:00:00Z"

scenes:
  - id: ch01_s01
    chapter: "第1章 喝酒不开车"
    title: "应酬酒桌上的陈总"
    summary: "35岁的陈汉升在建邺国际酒店参加应酬..."
    scene_type: [宴会]
    conflict: [利益]
    tension: 2
    pacing: 蓄力
    plot_function: [铺垫]
    characters: [陈汉升]
    emotion: [平静, 压抑]
    reader_effect: [会心一笑]
```

### 3. 构建倒排索引 (scenes_index.yaml)

为每个标签维度建立 值 → scene_id 列表 的映射：

```yaml
material_id: nm_xxx
total_scenes: 907
built_at: "2026-04-05T12:00:00Z"

# A. 内容层
scene_type:
  宴会: [ch01_s01, ch45_s02, ch302_s01]
  争吵: [ch05_s02, ch23_s01, ch156_s03]
  告白: [ch12_s01, ch445_s02]
  对决: [ch89_s01, ch302_s01]

conflict:
  利益: [ch01_s01, ch02_s01, ch56_s01]
  情感: [ch12_s01, ch45_s02]

stakes:
  荣辱: [ch01_s01, ch03_s02]

# B. 人物层
character:
  陈汉升: [ch01_s01, ch01_s02, ch01_s03, ...]
  萧容鱼: [ch03_s01, ch15_s02, ...]
  沈幼楚: [ch05_s01, ch12_s01, ...]

relationship:
  恋人: [ch12_s01, ch45_s02, ch156_s03]
  师徒: [ch89_s01]

interaction:
  对抗: [ch05_s02, ch89_s01]
  合作: [ch01_s01, ch45_s02]

power_dynamic:
  翻转: [ch302_s01, ch445_s03]

character_moment:
  道德抉择: [ch156_s03, ch445_s01]
  成长顿悟: [ch302_s01]

# C. 情感层
emotion:
  紧张: [ch05_s02, ch89_s01, ch302_s01]
  温馨: [ch45_s02, ch156_s01]

tension:
  5: [ch302_s01, ch445_s03, ch801_s01]
  4: [ch89_s01, ch156_s03]
  3: [ch01_s01, ch05_s02]

reader_effect:
  催泪: [ch445_s03, ch801_s02]
  爽感: [ch302_s01, ch500_s01]

# D. 结构层
plot_stage:
  开篇: [ch01_s01, ch01_s02, ch01_s03]
  "第一幕-发展": [ch05_s01, ch12_s01]

plot_function:
  伏笔埋设: [ch03_s02, ch45_s01, ch100_s01]
  伏笔回收: [ch302_s01, ch800_s01, ch956_s01]
  转折: [ch89_s01, ch302_s01]

pacing:
  爆发: [ch89_s01, ch302_s01]
  蓄力: [ch01_s01, ch05_s01]

# E. 技法层
technique:
  对比: [ch01_s01, ch156_s03]
  闪回: [ch45_s01, ch200_s02]

dialogue_type:
  争吵: [ch05_s02, ch23_s01]
  告白: [ch12_s01, ch445_s02]

# F. 物理层
setting:
  室内: [ch01_s01, ch05_s01]
  户外: [ch03_s01, ch45_s02]

scale:
  双人戏: [ch12_s01, ch45_s02]
  群戏: [ch01_s01, ch302_s01]

# 伏笔线索（如有 plot_threads）
plot_threads:
  "陈汉升身份秘密":
    plant: [ch03_s02, ch05_s01]
    develop: [ch45_s01, ch200_s02]
    payoff: [ch302_s01, ch800_s01]
```

### 4. 聚合全局人物索引 (character_index.yaml)

读取当前素材的 `characters.yaml`，提取每个角色的关键信息，写入 `data/character_index.yaml`。

如果 `character_index.yaml` 已有其他素材的条目，保留它们，只替换当前 material_id 的条目（upsert 语义）。

```yaml
# data/character_index.yaml
entries:
  - material_id: nm_novel_20260405_zhbk
    novel_name: "《书名》"
    characters:
      - name: 陈汉升
        role: protagonist
        archetype: 英雄
        traits: [果断, 重情义, 隐忍]
        moral_spectrum: 灰色
        arc_summary: "失意商人 → 重生逆袭 → 权力巅峰的孤独"
        arc_stages: 5
        appearance_count: 907        # 出场场景数（从 scenes_index character 维度统计）
        first_appearance: "第1章"
        narrative_function: 推动主线
      - name: 萧容鱼
        role: supporting
        archetype: 盟友
        traits: [聪慧, 外冷内热]
        moral_spectrum: 正义
        arc_summary: "冰山美女 → 逐渐信任 → 并肩作战"
        arc_stages: 3
        appearance_count: 245
        first_appearance: "第3章"
        narrative_function: 情感锚点
  - material_id: nm_novel_20260401_xxxx
    novel_name: "《另一本书》"
    characters: [...]
```

从 `characters.yaml` 的 `roster` 中提取字段，`arc_summary` 是将 `arc` 的阶段链浓缩为一句话描述。`appearance_count` 从 `scenes_index.yaml` 的 `character` 维度统计。

### 5. 聚合全局剧情索引 (plot_index.yaml)

读取当前素材的 `outline.yaml` 和 `scenes_index.yaml`，提取剧情结构信息，写入 `data/plot_index.yaml`。

同样采用 upsert 语义。

```yaml
# data/plot_index.yaml
entries:
  - material_id: nm_novel_20260405_zhbk
    novel_name: "《书名》"
    genre: [都市, 重生]           # 从 tags.yaml 读取
    total_scenes: 907
    structure:
      plot_stages:                # 各阶段场景分布
        开篇: 15
        第一幕-诱因: 45
        第一幕-发展: 120
        第二幕-对抗: 280
        中点: 30
        第二幕-低谷: 150
        第三幕-高潮: 180
        第三幕-收束: 70
        尾声: 17
      turning_points:             # 主要转折点（从 outline.yaml 提取）
        - chapter: 89
          description: "身份暴露"
          plot_function: 转折
        - chapter: 302
          description: "全面反击"
          plot_function: 高潮
      foreshadowing_count: 42     # 伏笔总数
      foreshadowing_resolved: 38  # 已回收伏笔数
    dominant_functions:            # 高频情节功能 Top-5
      - {function: 铺垫, count: 320}
      - {function: 升级, count: 210}
      - {function: 转折, count: 85}
      - {function: 伏笔埋设, count: 78}
      - {function: 伏笔回收, count: 65}
    pacing_profile:               # 节奏概况
      avg_tension: 3.2
      peak_tension_chapter: 302
      tension_variance: 1.1
```

### 6. 更新 meta.yaml

```yaml
pipeline:
  index_built: true
  index_at: "2026-04-05T12:00:00Z"
  manifest_scenes: 907
  global_indexes_updated: true
```

## 增量更新

如果后续新增了场景（continue 模式），`build-index` 支持增量更新：
1. 读取现有 manifest 和 index
2. 扫描 scenes/ 中不在 manifest 里的新文件
3. 只处理新增部分，合并到现有索引

## 输出格式

```
✅ 索引构建完成

📚 素材：{name}
📊 场景索引：
  场景总数：907
  标签维度：19
  人物索引：{n} 个角色
  伏笔线索：{n} 条

📊 全局索引已更新：
  👥 character_index.yaml — {n} 个角色（本素材）
  📖 plot_index.yaml — {转折点数}/{伏笔数}

📄 倒排索引：data/novels/{id}/scenes_index.yaml
📄 场景清单：data/novels/{id}/scenes_manifest.yaml
📄 全局人物：data/character_index.yaml
📄 全局剧情：data/plot_index.yaml
```

## 注意事项

- 分批读取场景文件（每批 50 个），避免 token 溢出
- 倒排索引中 scene_id 列表按章节顺序排列
- manifest 中 summary 截断到 50 字以内
- 索引文件需与实际场景保持一致，新增场景后需重建或增量更新
- `material-search-scene` 检索时应优先调用 `scripts/search.py` 查 SQLite，而非直接读 YAML 索引
- 全局索引采用 upsert 语义——只替换当前 material_id 的条目，保留其他素材数据
- `character_index` 中的 `arc_summary` 应浓缩为一句话，不超过 30 字
- `plot_index` 中的 `turning_points` 只记录主要转折（通常 3-8 个），不穷举
- **SQLite 是 YAML 的派生产物**：如果 `material.db` 丢失或损坏，运行 `python scripts/build_db.py` 可从 YAML 完全重建
- **增量更新**：单本小说修改后，用 `python scripts/build_db.py --incremental {material_id}` 更新，不必全量重建

## References

- [scripts/build_scene_index.py](../../../scripts/build_scene_index.py) — 固化索引脚本
- [scenes-index.schema.yaml](../../../docs/schemas/scenes-index.schema.yaml)
- [scenes-manifest.schema.yaml](../../../docs/schemas/scenes-manifest.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
