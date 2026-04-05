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

## 前置检查

1. 读取 `data/novels/{material_id}/meta.yaml`，确认 scenes 已完成（或部分完成）
2. 确认 `scenes/` 目录下有场景文件

## 输出文件

- `data/novels/{material_id}/scenes_index.yaml` — 倒排索引（标签 → scene_id 列表）
- `data/novels/{material_id}/scenes_manifest.yaml` — 场景清单（压缩视图）

遵循对应 schema：
- `docs/schemas/scenes-index.schema.yaml`
- `docs/schemas/scenes-manifest.schema.yaml`

## 执行步骤

### 1. 遍历场景文件

分批读取 `scenes/` 目录下所有 YAML 文件，每批 50 个。

从每个场景提取：
- `scene_id`, `chapter`, `title`, `summary`
- 全部标签字段（6 层 19 维）
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

### 4. 更新 meta.yaml

```yaml
pipeline:
  index_built: true
  index_at: "2026-04-05T12:00:00Z"
  manifest_scenes: 907
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
📊 索引统计：
  场景总数：907
  标签维度：19
  人物索引：{n} 个角色
  伏笔线索：{n} 条

📄 倒排索引：data/novels/{id}/scenes_index.yaml
📄 场景清单：data/novels/{id}/scenes_manifest.yaml
```

## 注意事项

- 分批读取场景文件（每批 50 个），避免 token 溢出
- 倒排索引中 scene_id 列表按章节顺序排列
- manifest 中 summary 截断到 50 字以内
- 索引文件需与实际场景保持一致，新增场景后需重建或增量更新
- `material-search-scene` 检索时应优先查 `scenes_index.yaml`

## References

- [scenes-index.schema.yaml](../../../docs/schemas/scenes-index.schema.yaml)
- [scenes-manifest.schema.yaml](../../../docs/schemas/scenes-manifest.schema.yaml)
- [AGENTS.md](../../AGENTS.md)
