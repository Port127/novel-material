# Novel Material Architecture

小说素材管理系统的架构拓扑。

## Topology

```text
                         user request
                              |
                              v
               +---------------------------+
               | L0: Dispatcher            |  轻量调度器
               +---------------------------+
               | novel-pipeline            |  模式路由 + 恢复判断
               +---------------------------+
                              |
                              v
               +---------------------------+
               | L1: Sub-Pipelines         |  子流水线（推荐入口）
               +---------------------------+
               | pipeline-ingest           |  material-add + source-format
               | pipeline-analyze          |  outline + worldbuilding + characters + tags
               | pipeline-scenes           |  novel-scenes(all) + build-index（可跨对话）
               | pipeline-finalize         |  refine + novel-stats
               +---------------------------+
                              |
                              v
               +---------------------------+
               | L2: Atomic Skills         |  原子操作
               +---------------------------+
               | material-add              |  入库
               | material-import           |  导入已分析素材
               | source-format             |  格式清洗
               | novel-outline             |  生成大纲
               | novel-worldbuilding       |  世界观设定
               | novel-characters          |  生成人物体系
               | novel-tags                |  小说级标签
               | novel-scenes              |  场景拆分+多维标签
               | build-index               |  构建索引
               | refine                    |  精调
               | novel-stats               |  统计报告+交互图表
               | material-search           |  关键词检索
               | material-search-scene     |  多维标签检索
               | material-search-context   |  写作上下文检索
               | tag-add / tag-merge       |  标签管理
               +---------------------------+
                              |
                              v
               +---------------------------+
               | L3: Global Data Store     |  全局数据
               +---------------------------+
               | data/index.yaml           |  总索引（路由层）
               | data/plot_index.yaml      |  剧情索引（auto-aggregated）
               | data/character_index.yaml |  人物索引（auto-aggregated）
               | data/tags.yaml            |  标签维度字典
               +---------------------------+
                              |
                              v
               +---------------------------+
               | L4: Query Layer (SQLite)  |  派生查询加速层
               +---------------------------+
               | data/material.db          |  结构化索引（从 YAML 构建）
               | scripts/core/search.py        |  多维检索接口
               | scripts/core/build_db.py      |  索引构建器
               | scripts/core/quality_audit.py |  批次质量审计
               +---------------------------+
                              |
                              v
               +-------------------------------+
               | L5: Per-Novel Store            |  每部小说独立文件夹
               +-------------------------------+
               | novels/{id}/meta.yaml          |  元数据
               | novels/{id}/source.txt         |  清洗后原文
               | novels/{id}/source.raw.txt     |  原始备份
               | novels/{id}/format_report.yaml |  清洗报告
               | novels/{id}/outline.yaml       |  大纲（+精调）
               | novels/{id}/worldbuilding.yaml |  世界观设定（+精调）
               | novels/{id}/characters.yaml    |  人物（+精调）
               | novels/{id}/tags.yaml          |  标签（+精调）
               | novels/{id}/scenes/*.yaml      |  场景
               | novels/{id}/scenes_index.yaml  |  倒排索引
               | novels/{id}/scenes_manifest.yaml| 场景清单
               | novels/{id}/stats.*            |  统计（yaml/md/html）
               +-------------------------------+
```

## Layers

### L0 — Dispatcher

轻量调度器，路由到子流水线：

| Skill | 职责 | 输入 | 输出 |
|-------|------|------|------|
| `novel-pipeline` | 模式路由 + 恢复判断 | 模式 + 参数 | 路由到子流水线 |

支持的流程模式：
- `full`: ingest → analyze → scenes → finalize
- `quick`: ingest → analyze
- `continue`: 从中断子流水线恢复
- `stage`: 执行指定子流水线

### L1 — Sub-Pipelines（推荐入口）

子流水线串联 2-4 个原子 skill，每个独立可恢复：

| Sub-Pipeline | 串联 skill | 产出 | 耗时 |
|--------------|-----------|------|------|
| `pipeline-ingest` | material-add → source-format | meta.yaml + source.txt | ~1分钟 |
| `pipeline-analyze` | outline → worldbuilding → characters → tags | 4个分析文件 | ~5-10分钟 |
| `pipeline-scenes` | novel-scenes(all) → build-index | scenes/*.yaml + 索引 | **可跨对话** |
| `pipeline-finalize` | refine → novel-stats | 精调文件 + stats.* | ~5分钟 |

**设计要点**：`pipeline-scenes` 是最耗时阶段（大书需要几十到上百批次），专门设计为可跨对话恢复。每 30 批建议开新对话。

### L2 — Atomic Skills

原子 skill 执行具体操作：

| Skill | 职责 | 输入 | 输出 |
|-------|------|------|------|
| `material-add` | 原文入库（status=raw） | 文件路径 | 文件夹 + meta.yaml + index.yaml |
| `material-import` | 导入已分析素材 | 文件夹路径 | 注册+校验+自动建索引 |
| `source-format` | 格式清洗 | material_id | 清洗后 source.txt + format_report.yaml |
| `novel-outline` | 生成大纲 | material_id | outline.yaml |
| `novel-worldbuilding` | 世界观设定 | material_id | worldbuilding.yaml |
| `novel-characters` | 生成人物体系 | material_id | characters.yaml |
| `novel-tags` | 小说级标签 | material_id | tags.yaml |
| `novel-scenes` | 场景拆分+标签 | material_id + 章节范围 | scenes/*.yaml |
| `build-index` | 构建索引 + 聚合全局索引 | material_id | scenes_index/manifest + character_index + plot_index |
| `refine` | 精调大纲/人物/标签/世界观 | material_id | 精调后的 outline/worldbuilding/characters/tags |
| `novel-stats` | 统计报告+交互图表 | material_id | stats.yaml + stats.md + stats.html |
| `material-search` | 关键词检索 | 关键词 | 匹配素材列表 |
| `material-search-scene` | 多维标签检索 | 标签条件 | 匹配场景列表 |
| `material-search-context` | 写作上下文检索 | 写作上下文 | 场景+人物+技法参考 |
| `tag-add` | 新增标签值 | 维度 + 值 | tags.yaml 更新 |
| `tag-merge` | 合并标签 | 旧值 + 新值 | 全局替换 |

### L3 — Global Data Store

| 文件 | 职责 |
|------|------|
| `data/index.yaml` | 素材路由表（material_id → 文件夹路径） |
| `data/plot_index.yaml` | 剧情索引（由 `build-index` 自动聚合） |
| `data/character_index.yaml` | 人物索引（由 `build-index` 自动聚合） |
| `data/tags.yaml` | 标签维度字典（定义合法维度和值） |

### L4 — Query Layer (SQLite)

`data/material.db` 是 YAML 的派生查询加速层，可随时从 YAML 重建。

#### scripts/ 目录结构

```
scripts/
├── core/               # 预制脚本（版本控制）
│   ├── search.py
│   ├── build_db.py
│   ├── build_scene_index.py
│   ├── quality_audit.py
│   ├── validate_yaml.py
│   └── source_format.py
├── generated/          # 运行时自动生成（.gitignore）
│   └── format_*.py
└── requirements.txt
```

| 脚本 | 职责 |
|------|------|
| `scripts/core/search.py` | 多维检索接口（场景/人物/全文） |
| `scripts/core/build_db.py` | 从 YAML 构建 SQLite |
| `scripts/core/build_scene_index.py` | 构建 YAML 倒排索引 |
| `scripts/core/quality_audit.py` | 批次质量审计 |
| `scripts/core/validate_yaml.py` | 场景 YAML 格式校验 |
| `scripts/core/source_format.py` | 格式清洗 |

### L5 — Per-Novel Store

每部小说独立文件夹 `data/novels/{material_id}/`：

| 文件 | 职责 | 生成者 |
|------|------|--------|
| `meta.yaml` | 元数据（书名、作者、状态、pipeline 进度） | `material-add` / `material-import` |
| `source.txt` | 清洗后原文 | `material-add` + `source-format` |
| `source.raw.txt` | 原始备份 | `source-format` |
| `format_report.yaml` | 格式清洗报告 | `source-format` |
| `chapter_index.yaml` | 章节索引（章号+标题+行号范围） | `source-format` |
| `outline.yaml` | 故事大纲（结构+节奏+伏笔） | `novel-outline` + `refine` |
| `worldbuilding.yaml` | 世界观设定（力量体系+地理+势力+背景） | `novel-worldbuilding` + `refine` |
| `characters.yaml` | 人物名册+关系网+弧线+原型+叙事功能 | `novel-characters` + `refine` |
| `tags.yaml` | 小说级多维标签 | `novel-tags` + `refine` |
| `scenes/*.yaml` | 场景（含6层20维标签+情节线索） | `novel-scenes` |
| `scenes_index.yaml` | 倒排索引（标签→场景ID） | `build-index` |
| `scenes_manifest.yaml` | 场景清单（压缩视图） | `build-index` |
| `stats.yaml` | 全书统计数据 | `novel-stats` |
| `stats.md` | 可视化报告（Mermaid） | `novel-stats` |
| `stats.html` | 交互报告（ECharts+关系图谱） | `novel-stats` |

### Schema Templates

所有 schema 模板存放在 `docs/schemas/`：

| Schema | 定义 |
|--------|------|
| `meta.schema.yaml` | 元数据结构 |
| `outline.schema.yaml` | 大纲结构 |
| `worldbuilding.schema.yaml` | 世界观设定结构 |
| `characters.schema.yaml` | 人物体系结构 |
| `scene.schema.yaml` | 场景结构（含完整标签体系+情节线索） |
| `novel-tags.schema.yaml` | 小说级标签结构 |
| `format-report.schema.yaml` | 格式清洗报告结构 |
| `scenes-index.schema.yaml` | 倒排索引结构 |
| `scenes-manifest.schema.yaml` | 场景清单结构 |
| `stats.schema.yaml` | 统计数据结构 |
| `character-index.schema.yaml` | 全局人物索引结构 |
| `plot-index.schema.yaml` | 全局剧情索引结构 |

## Tag System — 6 层 20 维（场景级）+ 7 维（小说级）

场景级标签体系（每个 scene.yaml 内）：

| 层 | 维度 | 用途 |
|----|------|------|
| A. 内容层 | scene_type, conflict, stakes | 发生了什么 |
| B. 人物层 | relationship, interaction, power_dynamic, character_moment, moral_spectrum | 谁和谁 |
| C. 情感层 | emotion, tension, reader_effect | 什么感受 |
| D. 结构层 | plot_stage, plot_function, pacing | 故事位置 |
| E. 技法层 | technique, dialogue_type, pov, info_delivery | 怎么写的 |
| F. 物理层 | setting, scale, time_weather | 什么环境 |

小说级标签（仅用于 novel-tags.yaml）：genre, tone, narrative_structure, time_handling, prose_style, writing_strength, tropes

合法值定义在 `data/tags.yaml`（20 维场景标签 + 7 维小说标签，共 418 值）。标签判断依据见 `docs/TAG_GUIDE.md`。

## Processing Pipeline

素材从入库到可检索的完整流程，拆分为 4 个子流水线：

```
┌─ pipeline-ingest ─────────────────────────────────────────┐
│  material-add          raw: 原文入库，创建文件夹           │
│         ↓                                                  │
│  source-format         raw: 格式清洗                       │
└────────────────────────────────────────────────────────────┘
         ↓
┌─ pipeline-analyze ────────────────────────────────────────┐
│  novel-outline         outlined: 生成大纲骨架              │
│         ↓                                                  │
│  novel-worldbuilding   outlined: 提取世界观设定            │
│         ↓                                                  │
│  novel-characters      outlined: 生成人物体系              │
│         ↓                                                  │
│  novel-tags            tagged: 生成小说级标签              │
└────────────────────────────────────────────────────────────┘
         ↓
┌─ pipeline-scenes（可跨对话）──────────────────────────────┐
│  novel-scenes          complete: 逐章拆分场景+打标签      │
│         ↓              （自动循环分批，每30批建议分段）     │
│  build-index           complete: 构建倒排索引+场景清单    │
└────────────────────────────────────────────────────────────┘
         ↓
┌─ pipeline-finalize ───────────────────────────────────────┐
│  refine                refined: 精调大纲/世界观/人物/标签  │
│         ↓                                                  │
│  novel-stats           refined: 统计报告+交互图表+图谱     │
└────────────────────────────────────────────────────────────┘
         ↓
(auto-aggregate)         refined: 汇总到全局索引
```

每个子流水线可单独调用、独立恢复。大书（>300章）建议逐个子流水线执行。

**替代路径**：`material-import` 跳过整个 pipeline，直接从已分析文件注册到索引。

## Package Invariants

1. **子流水线作为首选入口** — 一键流程通过 4 个子流水线分段执行，调度器仅做路由
2. **原子 skill 作为基础操作** — 单独 skill 用于调试或特殊需求
3. **YAML 作为 Source of Truth** — 场景 YAML 是权威数据，SQLite 是派生索引
4. **ID 唯一性** — `nm_{type}_{YYYYMMDD}_{random4}` 格式
5. **标签从字典选取** — 场景标签和小说标签均取自 `data/tags.yaml`
6. **每部小说自治** — 独立文件夹，全局索引为汇总视图
7. **渐进处理** — 场景拆分自动循环分批（all 模式），状态字段追踪进度，支持中断恢复
8. **脚本优先检索** — 检索场景时优先调用 `scripts/core/search.py` 查 SQLite，LLM 不直接读大索引文件
9. **后处理不读原文** — `build-index`、`refine`、`novel-stats` 只读场景 YAML 数据
10. **批次质量审计** — 每批场景写入后由 `scripts/core/quality_audit.py --batch {本批范围}` 检查（只传本批范围，不传累积范围）
11. **跨对话恢复** — `pipeline-scenes` 每批持久化进度到 meta.yaml，每 30 批建议分段，下次 continue 自动定位恢复点
12. **导入校验** — `material-import` 必须重新生成 ID、校验标签合法性、检查去重后才注册

## Anti-Pattern: 模板糊弄

以下行为**严格禁止**，违反即视为任务失败：

1. **脚本代替理解**：写 Python/Shell 脚本用关键词匹配批量生成场景文件。场景标签必须由 LLM 阅读原文后判断，不可由脚本代劳。
2. **千篇一律**：所有场景的 `scene_type` / `emotion` / `conflict` / `setting` 等字段值相同或高度雷同。同一批次内每个场景的标签组合必须反映该场景的独特内容。
3. **空字段占位**：`conflict: []`、`stakes: []`、`action: ''` 等空值大面积出现。如果确实无冲突，写 `conflict: []` 可以，但不能所有场景都是空的。
4. **summary 抄首句**：summary 不能只是章节开头几十个字的截断，必须是对场景核心事件的概括。
5. **title 编号代替**：`title: 场景1` 不合格，必须是有语义的概括短语（如 "庙会买糖葫芦"、"车祸觉醒系统"）。

**合规检查**：完成一批后，抽查该批内任意 2 个场景文件，确认标签组合互不相同。如果相同，必须重做该批。

## Cross-project Integration

### 接入方式

`novel` 项目通过两种方式访问素材：

**推荐方式（脚本调用）**：
```bash
python ../novel-material/scripts/core/search.py scene --emotion 悲伤 --interaction 告别 --limit 5
python ../novel-material/scripts/core/search.py character --archetype 导师
python ../novel-material/scripts/core/search.py text --query 告别
```

**直接读取**（小规模/无 SQLite 时）：
```
../novel-material/data/index.yaml            # 找到素材文件夹
../novel-material/data/plot_index.yaml       # 跨小说剧情检索
../novel-material/data/character_index.yaml  # 跨小说人物检索
../novel-material/data/tags.yaml             # 标签字典
```

没有素材库时 `novel` 项目照常工作，所有依赖素材库的功能均为软依赖。

### 借鉴维度映射

`novel` 项目的 `inspiration-log` 使用 5 个借鉴维度，与本项目的标签体系对应：

| novel 借鉴维度 | novel-material 标签维度 | 说明 |
|---------------|----------------------|------|
| 设定 | `setting` + `scale` + worldbuilding | 空间环境 + 世界观设定 |
| 节奏 | `pacing` + `tension` + `plot_stage` | 节奏型 + 张力值 + 剧情阶段 |
| 冲突 | `conflict` + `stakes` + `power_dynamic` | 冲突类型 + 赌注 + 权力位差 |
| 结构 | `plot_function` + `technique` + `narrative_structure` | 情节功能 + 叙事技法 + 叙事结构 |
| 人物 | `archetype` + `character_moment` + `psychology.*` | 原型 + 弧光时刻 + 心理深度 |

`material-search-context` 在解析写作上下文时使用此映射自动展开检索维度。

### 风格桥接

`novel` 项目管理每部作品的写作风格，`novel-material` 的小说级标签中有对应维度：

| novel 风格需求 | novel-material 标签 |
|---------------|-------------------|
| 文笔参考 | `prose_style`（华丽/朴素/冷叙述/诗化/...） |
| 基调参考 | `tone`（沉重/轻快/冷峻/热血/...） |
| 长板参考 | `writing_strength`（人物塑造/对话/氛围营造/...） |
| 套路参考 | `tropes`（废柴逆袭/扮猪吃虎/重生复仇/...） |

检索场景时可同时用小说级标签缩小范围（如"找一个冷叙述风格的催泪场景"→ 先筛 `prose_style: 冷叙述` 的小说，再在其中检索 `reader_effect: 催泪`）。

## Architecture Decision Records

### ADR-1：YAML 为 Source of Truth，SQLite 为派生层

**决策**：场景 YAML 文件是权威数据源，`data/material.db`（SQLite）仅作为查询加速层，可随时从 YAML 重建。

**动机**：场景标签由 LLM 逐批阅读原文生成并写入 YAML，YAML 天然可 diff、可版本控制、可人工审查。如果让 SQLite 成为主存储，LLM 写入和人工校验都会变复杂。

**代价**：每次场景修改后需要重建 SQLite（`python scripts/core/build_db.py`）。对当前规模（数千场景）重建耗时 < 5 秒，可接受。

### ADR-2：嵌套 → 扁平 schema 迁移（2026-04）

**决策**：场景 YAML 从嵌套结构（content/people/emotion/structure/craft/setting 分组）迁移为扁平结构（所有标签维度平铺在顶层）。`scene.schema.yaml` 的 Flat Output Contract 定义了扁平格式。

**动机**：嵌套结构导致 `build_db.py` 和 `validate_yaml.py` 需要知道每个字段在哪个分组下，新增维度时要同步修改多处。扁平结构简化了脚本逻辑和 LLM 输出格式。

**代价**：存量数据可能存在嵌套格式。`build_db.py` 内置 `_flatten_scene()` 函数兼容两种格式，确保旧数据仍可入库。未来重跑 pipeline 时会自然迁移为扁平格式。

### ADR-3：场景标签必须 LLM 生成，禁止脚本批量生成（Anti-Pattern 根因）

**决策**：场景的多维标签必须由 LLM 逐批阅读原文后判断生成，禁止编写脚本通过关键词匹配批量填充。

**动机**：早期尝试中，脚本批量生成的标签千篇一律（所有场景 `emotion: [平静]`、`conflict: []`），完全丧失检索区分度。关键词匹配无法判断场景的深层语义（如"表面平静实则暗流涌动"应标 `tension: 3` 而非 `tension: 1`）。

**代价**：场景拆分是最耗时的阶段，1000 章的小说需要 100+ 批次、可能跨多次对话。通过 `pipeline-scenes` 的跨对话恢复机制缓解。

### ADR-4：scripts/ 拆分 core vs generated（2026-04）

**决策**：预制脚本放 `scripts/core/`（纳入版本控制），运行时自动生成的脚本放 `scripts/generated/`（gitignore）。

**动机**：`source-format` 等 skill 会针对特定小说的格式问题动态生成补充脚本（如 `format_dafeng.py`），这些脚本与预制的通用脚本混在一起，难以区分哪些该提交、哪些是临时产物。

**代价**：所有引用预制脚本的文档和 skill 都需要将路径从 `scripts/xxx.py` 改为 `scripts/core/xxx.py`。一次性迁移成本，长期无额外代价。
