# Novel Material - Agent Map

独立的小说素材管理系统，为多个小说项目提供共享素材检索服务。

## Priorities

1. 用户当前请求
2. 本文件
3. `ARCHITECTURE.md`
4. 目标 skill 的 `SKILL.md`

## Quick Start

```bash
# 一键流程（推荐）
/novel-pipeline full [路径]        # 一键完整处理（入库→格式化→大纲→人物→标签→场景→索引→精调→统计）
/novel-pipeline quick [路径]       # 快速骨架处理（入库→格式化→大纲→人物）
/novel-pipeline continue [id]      # 从中断点恢复
/novel-pipeline stage [id] [阶段]  # 执行指定阶段

# 单独调用（适合调试或特殊需求）
/material-add [路径]                    # 添加素材入库
/source-format [material_id]            # 格式清洗（繁简/广告/章节名/缺章检测）
/novel-outline [material_id]            # 生成故事大纲
/novel-characters [material_id]         # 生成人物体系
/novel-tags [material_id]               # 生成小说级标签
/novel-scenes [material_id] [章节范围]   # 拆分场景+打标签
/build-index [material_id]              # 构建倒排索引+场景清单
/refine [material_id]                   # 精调大纲/人物/标签（基于场景数据）
/novel-stats [material_id]              # 生成统计报告+可视化

# 检索
/material-search [关键词]        # 关键词检索
/material-search-scene [需求描述] # 多维标签检索
```

## Skills

|| Skill | 用途 |
||-------|------|
|| `novel-pipeline` | 一键流程编排，支持完整/快速/恢复模式 |
|| `material-add` | 添加素材入库 |
|| `source-format` | 格式清洗（繁简/广告/引号/章节名/缺章检测） |
|| `novel-outline` | 生成故事大纲（结构+节奏+伏笔） |
|| `novel-characters` | 生成人物体系（名册+关系+弧线） |
|| `novel-tags` | 生成小说级多维标签 |
|| `novel-scenes` | 拆分场景+多维标签（分批执行） |
|| `build-index` | 构建倒排索引+场景清单（加速检索） |
|| `refine` | 场景完成后精调大纲/人物/标签 |
|| `novel-stats` | 生成统计报告+可视化图表 |
|| `material-search` | 关键词检索 |
|| `material-search-scene` | 按多维标签检索场景 |
|| `tag-add` | 新增标签值 |
|| `tag-merge` | 合并同义标签 |

## Architecture

见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## Key Docs

|| 文档 | 用途 |
||------|------|
|| [docs/DESIGN.md](docs/DESIGN.md) | 系统设计 |
|| [docs/schemas/](docs/schemas/) | 数据 schema 模板 |
|| [docs/PLANS.md](docs/PLANS.md) | 路线图 + 执行计划 |

## Data Store

```
data/
├── index.yaml                    # 素材路由表
├── plot_index.yaml               # 剧情索引（自动汇总）
├── character_index.yaml          # 人物索引（自动汇总）
├── tags.yaml                     # 标签维度字典（6层19维）
└── novels/
    └── {material_id}/
        ├── meta.yaml             # 元数据
        ├── source.txt            # 清洗后原文
        ├── source.raw.txt        # 原始备份
        ├── format_report.yaml    # 格式清洗报告
        ├── outline.yaml          # 大纲（精调后含伏笔网络+节奏曲线）
        ├── characters.yaml       # 人物体系（精调后含精确弧线）
        ├── tags.yaml             # 小说级标签（精调后含统计校准）
        ├── scenes_index.yaml     # 倒排索引（标签→场景ID）
        ├── scenes_manifest.yaml  # 场景清单（压缩视图）
        ├── stats.yaml            # 统计数据
        ├── stats.md              # 可视化报告
        └── scenes/*.yaml         # 场景（含多维标签+情节线索）
```

## Processing Pipeline

```
material-add → source-format → novel-outline → novel-characters → novel-tags → novel-scenes → build-index → refine → novel-stats
   (raw)          (raw)         (outlined)       (outlined)        (tagged)     (complete)     (complete)   (refined)  (refined)
```

`novel-scenes` 可按章节范围分批执行，不必一次处理全书。
`build-index` / `refine` / `novel-stats` 在场景全部完成后执行，不读原文，只读场景数据。

## ID Convention

格式：`nm_{type}_{YYYYMMDD}_{random4}`

示例：`nm_novel_20260404_a1b2`

## Cross-project Access

```
../novel-material/data/index.yaml              # 素材路由
../novel-material/data/plot_index.yaml         # 剧情检索
../novel-material/data/character_index.yaml    # 人物检索
../novel-material/data/tags.yaml               # 标签字典
```

## Hard Rules

- MUST 使用 skills 执行操作
- MUST 素材 ID 遵循命名规范
- MUST 标签从 `data/tags.yaml` 字典中选取
- MUST 场景拆分遵循 `docs/schemas/scene.schema.yaml`
- MUST 检索优先查 `scenes_index.yaml`，不遍历全部场景文件
- MUST refine/stats/build-index 不读原文，只读场景 YAML
- NEVER 编造质量数据（无信号写 TBD）
- NEVER 一次处理全书场景（分批执行）
