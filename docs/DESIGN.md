# Novel Material 设计文档

## 系统定位

**独立的小说素材管理系统**，为多个小说项目提供共享素材检索服务。

核心价值：
- 素材集中管理，跨项目复用
- 按场景多维标签检索（6 层 19 维）
- 人物原型与关系网检索
- 标签规范化治理

## 设计原则

### 仓库即记录系统

所有素材、索引、标签均存储在仓库内，Agent 运行时无需外部依赖。

### Skills 作为唯一入口

13 个 skills 封装所有操作：
- 入库：`material-add`
- 清洗：`source-format`
- 分析：`novel-outline`, `novel-characters`, `novel-tags`, `novel-scenes`
- 后处理：`build-index`, `refine`, `novel-stats`
- 检索：`material-search`, `material-search-scene`
- 标签治理：`tag-add`, `tag-merge`

### 每部小说自治

每部小说独立文件夹 `data/novels/{material_id}/`，包含：
- 原文（清洗后）、元数据、格式清洗报告
- 大纲（含结构、节奏、伏笔追踪，精调后含伏笔网络）
- 人物体系（含名册、关系网、弧线，精调后含精确时间线）
- 小说级标签（精调后含统计校准）
- 场景集（每个场景含多维标签+情节线索）
- 索引文件（倒排索引+场景清单，加速检索）
- 统计报告（全书统计数据+可视化）

全局索引（`plot_index.yaml`, `character_index.yaml`）为自动汇总视图。

### 渐进处理

场景拆分可分批执行。`meta.yaml` 中 `status` 字段追踪进度：
- `raw` → 仅有原文（可能已格式化）
- `outlined` → 大纲 + 人物已完成
- `tagged` → 场景拆分 + 标签已完成
- `complete` → 场景全部完成，索引已构建
- `refined` → 精调完成，统计报告已生成

### 渐进披露

Layer 1：Skill 元数据（`SKILL.md` frontmatter）
Layer 2：`AGENTS.md` — 稳定路由
Layer 3：`docs/` — 设计、schema、计划
Layer 4：`data/` — 索引、素材存储

### ID 规范

素材 ID 格式：`nm_{type}_{YYYYMMDD}_{random4}`

## 数据模型

### 素材索引 (`data/index.yaml`)

路由层，记录 material_id → 文件夹路径：

```yaml
materials:
  - id: nm_novel_20260404_a1b2
    type: novel
    name: "《书名》"
    author: 作者名
    folder: data/novels/nm_novel_20260404_a1b2
    status: raw
    added: 2026-04-04
```

### 小说文件夹结构

```
data/novels/{material_id}/
├── meta.yaml          # 元数据
├── source.txt         # 原文
├── outline.yaml       # 大纲（结构+节奏+伏笔）
├── characters.yaml    # 人物（名册+关系+弧线）
├── tags.yaml          # 小说级多维标签
└── scenes/            # 场景集
    ├── ch01_s01.yaml
    ├── ch01_s02.yaml
    └── ...
```

### 标签体系 (`data/tags.yaml`)

6 层 19 维，从写作者检索视角设计：

| 层 | 维度 | 回答什么 |
|----|------|---------|
| A. 内容 | scene_type, conflict, stakes | 发生了什么 |
| B. 人物 | relationship, interaction, power_dynamic, character_moment, moral_spectrum | 谁和谁 |
| C. 情感 | emotion, tension, reader_effect | 什么感受 |
| D. 结构 | plot_stage, plot_function, pacing | 在故事哪里 |
| E. 技法 | technique, dialogue_type, pov, info_delivery | 怎么写的 |
| F. 物理 | setting, scale, time_weather | 什么环境 |

### 检索策略

#### 关键词检索 (`material-search`)

匹配 `name`, `summary`, scene `title` 和 `summary`。

#### 多维标签检索 (`material-search-scene`)

1. 解析自然语言需求为标签组合
2. **优先查 `scenes_index.yaml` 倒排索引**，命中候选 scene_id
3. 只读取候选场景的完整 YAML 确认匹配
4. 按匹配度排序返回候选场景

若无倒排索引，退回到遍历 `scenes_manifest.yaml` 或 `scenes/*.yaml`。

示例：
- "恋爱中吵架" → `relationship: 恋人` + `scene_type: 争吵`
- "弱者反杀强者" → `power_dynamic: 翻转` + `scene_type: 对决`
- "催泪但不煽情" → `reader_effect: 催泪` + `technique: 留白`

## Schema

所有 schema 模板存放在 `docs/schemas/`：

| Schema | 用途 |
|--------|------|
| `meta.schema.yaml` | 元数据 |
| `outline.schema.yaml` | 大纲 |
| `characters.schema.yaml` | 人物 |
| `scene.schema.yaml` | 场景（含情节线索） |
| `novel-tags.schema.yaml` | 小说级标签 |
| `format-report.schema.yaml` | 格式清洗报告 |
| `scenes-index.schema.yaml` | 倒排索引 |
| `scenes-manifest.schema.yaml` | 场景清单 |
| `stats.schema.yaml` | 统计数据 |

## 相关文档

- [AGENTS.md](../AGENTS.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
