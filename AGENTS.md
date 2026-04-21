# Novel Material - Agent Map

独立的小说素材管理系统，为多个小说项目提供共享素材检索服务。

## Priorities

1. 用户当前请求
2. 本文件
3. `ARCHITECTURE.md`
4. 目标 skill 的 `SKILL.md`

## 文档导航

| 你想做什么 | 去哪里 |
|-----------|-------|
| 看项目全貌 | `README.md` |
| 按事件找命令 | `docs/USAGE-GUIDE.md` |
| 了解系统架构 / 标签体系 / ADR | `ARCHITECTURE.md` |
| 标签标注时查判断依据 | `docs/TAG_GUIDE.md` |
| 查数据 schema | `docs/schemas/` |
| 直接查数据库 | `docs/USAGE-GUIDE.md` §七 |

## Quick Start

```bash
# ── 一键流程（调度器，串联 4 个子流水线）──
/novel-pipeline full [路径]          # 一键完整处理
/novel-pipeline quick [路径]         # 快速骨架（入库→分析）
/novel-pipeline continue [id]        # 从中断点恢复
/novel-pipeline stage [id] [阶段]    # 执行指定子流水线

# ── 子流水线（推荐大书分段处理）──
/pipeline-ingest [路径]              # ① 入库+格式清洗
/pipeline-analyze [material_id]      # ② 大纲+世界观+人物+标签
/pipeline-events [material_id]       # ③ 全书事件拆分+索引（可跨对话恢复）
/pipeline-finalize [material_id]     # ④ 精调+统计报告

# ── 导入 ──
/material-import [文件夹路径]         # 导入外部已按 schema 分析好的素材

# ── 原子 skill（调试/特殊需求）──
/material-add [路径]                 # 仅入库原文
/material-delete [material_id]       # 删除素材+清理所有关联
/source-format [material_id]         # 格式清洗
/novel-outline [material_id]         # 生成故事大纲
/novel-worldbuilding [material_id]   # 提取世界观设定
/novel-characters [material_id]      # 生成人物体系
/novel-tags [material_id]            # 生成小说级标签
/novel-events [material_id] [范围]   # 拆分事件+打标签
/build-index [material_id]           # 构建倒排索引+事件清单
/refine [material_id]                # 精调大纲/人物/标签
/novel-stats [material_id]           # 生成统计报告+可视化

# ── 检索 ──
/material-search [关键词]            # 关键词检索
/material-search-event [需求描述]    # 多维标签检索
/material-search-context [写作上下文] # 写作事件上下文检索
```

## Skills

### 调度层

| Skill | 用途 |
|-------|------|
| `novel-pipeline` | 轻量调度器，路由到子流水线 |

### 子流水线层（推荐入口）

| Skill | 串联的原子 skill | 用途 |
|-------|-------------------|------|
| `pipeline-ingest` | material-add → source-format | 入库+格式清洗 |
| `pipeline-analyze` | outline → worldbuilding → characters → tags | 生成骨架分析 |
| `pipeline-events` | novel-events (all) → build-index | 全书事件拆分+索引（可跨对话） |
| `pipeline-finalize` | refine → novel-stats | 精调+统计报告 |

### 导入

| Skill | 用途 |
|-------|------|
| `material-import` | 导入外部已分析好的素材（按本库 schema），自动注册+建索引 |

### 原子 skill 层

| 分类 | Skill | 用途 |
|------|-------|------|
| 入库 | `material-add` | 添加原文入库（status=raw，需后续跑 pipeline） |
| 删除 | `material-delete` | 删除素材及其所有关联资源（文件夹+索引+数据库） |
| 清洗 | `source-format` | 格式清洗（繁简/广告/引号/章节名/缺章检测） |
| 分析 | `novel-outline` | 生成故事大纲（**文件夹结构**：结构+节奏+钩子+可选模块） |
| 分析 | `novel-worldbuilding` | 提取世界观设定（**文件夹结构**：力量体系+地理+势力+背景知识） |
| 分析 | `novel-characters` | 生成人物体系（**文件夹结构**：索引+人物小传+关系网） |
| 分析 | `novel-tags` | 生成小说级多维标签（含套路识别） |
| 事件 | `novel-events` | 拆分事件+多维标签（分批执行） |
| 索引 | `build-index` | 构建倒排索引+事件清单（支持文件夹结构） |
| 后处理 | `refine` | 事件完成后精调大纲/人物/世界观（**调整而非增量**） |
| 后处理 | `novel-stats` | 生成统计报告+可视化图表+交互HTML+关系图谱 |
| 检索 | `material-search` | 关键词检索 |
| 检索 | `material-search-event` | 按多维标签检索事件 |
| 检索 | `material-search-context` | 写作上下文检索（事件+人物+技法三维） |
| 标签 | `tag-add` | 新增标签值 |
| 标签 | `tag-merge` | 合并同义标签 |

## ID Convention

格式：`nm_{type}_{YYYYMMDD}_{random4}`

## Hard Rules

- MUST 使用 skills 执行操作
- MUST 素材 ID 遵循命名规范
- MUST 标签从 `data/tags.yaml` 字典中选取
- MUST 事件拆分遵循 `docs/schemas/event-unit.schema.yaml` 的格式
- MUST 事件 YAML 写入后执行格式校验（YAML 解析 + 必填字段 + 标签合法 + 章节名匹配）
- MUST 事件 `chapter` 字段从 `chapter_index.yaml` 逐字拷贝，禁止凭记忆拼写
- MUST 事件 YAML 中含引号的字符串值用单引号包裹，防止 YAML 解析失败
- MUST 检索优先调用 `scripts/core/search.py` 查 SQLite，不直接读大索引文件
- MUST refine/stats/build-index 不读原文，只读事件 YAML
- MUST 事件拆分通过自动循环分批执行，all 模式下无需逐批确认
- MUST 每批事件写入后运行 `scripts/core/quality_audit.py --batch {本批范围}` 审计（只传本批范围如 `181-200`，不传累积范围如 `1-200`）
- MUST build-index 同时生成 YAML 索引和 SQLite（`data/material.db`）
- MUST 事件标签由 LLM 逐批阅读原文后生成，禁止关键词匹配代替理解
- MUST material-import 重新生成 material_id，校验标签合法性后才注册
- MUST outline/、worldbuilding/、characters/ 使用文件夹结构（`_index.yaml` + 各模块）
- MUST `_index.yaml` 存概览和统计，SQLite 存完整索引，各司其职
- MUST 人物小传 key_events 只记录关键节点（≤10个），避免膨胀
- MUST refine 是调整而非增量，可删除、合并、重构，不无限膨胀
- MUST 粒度自适应：地理/势力 ≤3 用单文件，>3 用文件夹
- NEVER 编造质量数据（无信号写 TBD）
- NEVER 用脚本批量生成模板化事件文件（详见 `ARCHITECTURE.md` → Anti-Pattern）
- NEVER 跨素材共享世界观/人物（每个素材独立）

## 护栏

- 保持本文件为地图，而非百科全书
- 链接指向细节，而非重复内容
- 架构决策、设计原则、Anti-Pattern 详情均在 `ARCHITECTURE.md`
