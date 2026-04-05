# Novel Material Architecture

小说素材管理系统的架构拓扑。

## Topology

```text
                         user request
                              |
                              v
               +---------------------------+
               | Pipeline Layer            |  --> 一键流程编排
               +---------------------------+
               | novel-pipeline            |  --> 流程路由 + 阶段门禁
               +---------------------------+
                              |
                              v
               +---------------------------+
               | Skills Layer              |
               +---------------------------+
               | material-add              |  --> 入库
               | source-format             |  --> 格式清洗
               | novel-outline             |  --> 生成大纲
               | novel-characters          |  --> 生成人物体系
               | novel-tags                |  --> 小说级标签
               | novel-scenes              |  --> 场景拆分+多维标签
               | build-index               |  --> 构建索引
               | refine                    |  --> 精调大纲/人物/标签
               | novel-stats               |  --> 统计报告
               | material-search           |  --> 关键词检索
               | material-search-scene     |  --> 多维标签检索
               | tag-add                   |  --> 新增标签
               | tag-merge                 |  --> 合并标签
               +---------------------------+
                              |
                              v
               +---------------------------+
               | Data Store (YAML)         |
               +---------------------------+
               | data/index.yaml           |  总索引（路由层）
               | data/plot_index.yaml      |  剧情索引（planned）
               | data/character_index.yaml |  人物索引（planned）
               | data/tags.yaml            |  标签维度字典
               +---------------------------+
                              |
                              v
               +-------------------------------+
               | Per-Novel Store               |
               +-------------------------------+
               | novels/{id}/meta.yaml         |  元数据
               | novels/{id}/source.txt        |  清洗后原文
               | novels/{id}/source.raw.txt    |  原始备份
               | novels/{id}/format_report.yaml|  清洗报告
               | novels/{id}/outline.yaml      |  大纲（+精调）
               | novels/{id}/characters.yaml   |  人物（+精调）
               | novels/{id}/tags.yaml         |  标签（+精调）
               | novels/{id}/scenes/*.yaml     |  场景
               | novels/{id}/scenes_index.yaml |  倒排索引
               | novels/{id}/scenes_manifest.yaml |  场景清单
               | novels/{id}/stats.yaml        |  统计数据
               | novels/{id}/stats.md          |  可视化报告
               +-------------------------------+
```

## Layers

### Layer 0 — Pipeline (Entry)

一键流程编排入口：

|| Skill | 职责 | 输入 | 输出 |
||-------|------|------|------|
|| `novel-pipeline` | 流程路由 + 阶段门禁 | 模式 + 参数 | 执行报告 |

支持的流程模式：
- `full`: material-add → source-format → outline → characters → tags → scenes → build-index → refine → novel-stats
- `quick`: material-add → source-format → outline → characters
- `continue`: 从中断点恢复
- `stage`: 执行指定阶段

### Layer 1 — Skills (Operation)

Skills 作为具体操作执行者：

|| Skill | 职责 | 输入 | 输出 |
||-------|------|------|------|
|| `material-add` | 素材入库 | 文件路径 | 文件夹 + meta.yaml + index.yaml |
|| `source-format` | 格式清洗 | material_id | 清洗后 source.txt + format_report.yaml |
|| `novel-outline` | 生成大纲 | material_id | outline.yaml |
|| `novel-characters` | 生成人物体系 | material_id | characters.yaml |
|| `novel-tags` | 小说级标签 | material_id | tags.yaml |
|| `novel-scenes` | 场景拆分+标签 | material_id + 章节范围 | scenes/*.yaml |
|| `build-index` | 构建索引 | material_id | scenes_index.yaml + scenes_manifest.yaml |
|| `refine` | 精调大纲/人物/标签 | material_id | 精调后的 outline/characters/tags |
|| `novel-stats` | 统计报告 | material_id | stats.yaml + stats.md |
|| `material-search` | 关键词检索 | 关键词 | 匹配素材列表 |
|| `material-search-scene` | 多维标签检索 | 标签条件 | 匹配场景列表 |
|| `tag-add` | 新增标签值 | 维度 + 值 | tags.yaml 更新 |
|| `tag-merge` | 合并标签 | 旧值 + 新值 | 全局替换 |

### Layer 2 — Global Data Store

|| 文件 | 职责 |
||------|------|
|| `data/index.yaml` | 素材路由表（material_id → 文件夹路径） |
|| `data/plot_index.yaml` | 剧情索引（planned，从 scenes 自动汇总） |
|| `data/character_index.yaml` | 人物索引（planned，从 characters 自动汇总） |
|| `data/tags.yaml` | 标签维度字典（定义合法维度和值） |

### Layer 3 — Per-Novel Store

每部小说独立文件夹 `data/novels/{material_id}/`：

|| 文件 | 职责 | 生成者 |
||------|------|--------|
|| `meta.yaml` | 元数据（书名、作者、状态） | `material-add` |
|| `source.txt` | 清洗后原文 | `material-add` + `source-format` |
|| `source.raw.txt` | 原始备份 | `source-format` |
|| `format_report.yaml` | 格式清洗报告 | `source-format` |
|| `outline.yaml` | 故事大纲（结构+节奏+伏笔） | `novel-outline` + `refine` |
|| `characters.yaml` | 人物名册+关系网+弧线 | `novel-characters` + `refine` |
|| `tags.yaml` | 小说级多维标签 | `novel-tags` + `refine` |
|| `scenes/*.yaml` | 场景（含6层19维标签+情节线索） | `novel-scenes` |
|| `scenes_index.yaml` | 倒排索引（标签→场景ID） | `build-index` |
|| `scenes_manifest.yaml` | 场景清单（压缩视图） | `build-index` |
|| `stats.yaml` | 全书统计数据 | `novel-stats` |
|| `stats.md` | 可视化报告 | `novel-stats` |

### Schema Templates

所有 schema 模板存放在 `docs/schemas/`：

|| Schema | 定义 |
||--------|------|
|| `meta.schema.yaml` | 元数据结构 |
|| `outline.schema.yaml` | 大纲结构 |
|| `characters.schema.yaml` | 人物体系结构 |
|| `scene.schema.yaml` | 场景结构（含完整标签体系+情节线索） |
|| `novel-tags.schema.yaml` | 小说级标签结构 |
|| `format-report.schema.yaml` | 格式清洗报告结构 |
|| `scenes-index.schema.yaml` | 倒排索引结构 |
|| `scenes-manifest.schema.yaml` | 场景清单结构 |
|| `stats.schema.yaml` | 统计数据结构 |

## Tag System — 6 层 19 维

场景级标签体系（每个 scene.yaml 内）：

| 层 | 维度 | 用途 |
|----|------|------|
| A. 内容层 | scene_type, conflict, stakes | 发生了什么 |
| B. 人物层 | relationship, interaction, power_dynamic, character_moment, moral_spectrum | 谁和谁 |
| C. 情感层 | emotion, tension, reader_effect | 什么感受 |
| D. 结构层 | plot_stage, plot_function, pacing | 故事位置 |
| E. 技法层 | technique, dialogue_type, pov, info_delivery | 怎么写的 |
| F. 物理层 | setting, scale, time_weather | 什么环境 |

合法值定义在 `data/tags.yaml`。

## Processing Pipeline

素材从入库到可检索的完整流程：

```
material-add          raw: 原文入库，创建文件夹
       ↓
source-format         raw: 格式清洗（繁简/广告/引号/章节名/缺章检测）
       ↓
novel-outline         outlined: 生成大纲骨架
       ↓
novel-characters      outlined: 生成人物体系
       ↓
novel-tags            tagged: 生成小说级标签
       ↓
novel-scenes          complete: 逐章拆分场景+打标签
       ↓
build-index           complete: 构建倒排索引+场景清单
       ↓
refine                refined: 精调大纲/人物/标签（基于场景数据）
       ↓
novel-stats           refined: 生成统计报告+可视化
       ↓
(auto-aggregate)      refined: 汇总到全局索引
```

注意：`novel-scenes` 支持 `all` 模式自动循环分批处理全书，也可手动指定章节范围。

## Package Invariants

1. **Orchestrator 作为首选入口** — 一键流程通过 orchestrator 执行
2. **Skills 作为原子操作** — 单独 skill 用于调试或特殊需求
3. **YAML 作为记录系统** — 不依赖聊天/外部文档
4. **ID 唯一性** — `nm_{type}_{YYYYMMDD}_{random4}` 格式
5. **标签从字典选取** — 场景标签和小说标签均取自 `data/tags.yaml`
6. **每部小说自治** — 独立文件夹，全局索引为汇总视图
7. **渐进处理** — 场景拆分自动循环分批（all 模式），状态字段追踪进度，支持中断恢复
8. **索引优先检索** — 检索场景时优先查 `scenes_index.yaml`，避免遍历全部场景文件
9. **后处理不读原文** — `build-index`、`refine`、`novel-stats` 只读场景 YAML 数据

## Cross-project Integration

小说项目通过 `index.yaml` 路由：

```
../novel-material/data/index.yaml            # 找到素材文件夹
../novel-material/data/plot_index.yaml       # 跨小说剧情检索
../novel-material/data/character_index.yaml  # 跨小说人物检索
../novel-material/data/tags.yaml             # 标签字典
```
