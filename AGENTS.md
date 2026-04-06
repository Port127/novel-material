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
/novel-pipeline full [路径]        # 一键完整处理（10 阶段）
/novel-pipeline quick [路径]       # 快速骨架（入库→格式化→大纲→世界观→人物）
/novel-pipeline continue [id]      # 从中断点恢复
/novel-pipeline stage [id] [阶段]  # 执行指定阶段

# 单独调用
/material-add [路径]                    # 添加素材入库
/source-format [material_id]            # 格式清洗
/novel-outline [material_id]            # 生成故事大纲
/novel-worldbuilding [material_id]     # 提取世界观设定
/novel-characters [material_id]         # 生成人物体系
/novel-tags [material_id]               # 生成小说级标签
/novel-scenes [material_id] [章节范围]   # 拆分场景+打标签
/build-index [material_id]              # 构建倒排索引+场景清单
/refine [material_id]                   # 精调大纲/人物/标签
/novel-stats [material_id]              # 生成统计报告+可视化

# 检索
/material-search [关键词]         # 关键词检索
/material-search-scene [需求描述] # 多维标签检索
```

## Skills

|| Skill | 用途 |
||-------|------|
|| `novel-pipeline` | 一键流程编排，支持完整/快速/恢复模式 |
|| `material-add` | 添加素材入库 |
|| `source-format` | 格式清洗（繁简/广告/引号/章节名/缺章检测） |
|| `novel-outline` | 生成故事大纲（结构+节奏+伏笔） |
|| `novel-worldbuilding` | 提取世界观设定（力量体系+地理+势力+背景） |
|| `novel-characters` | 生成人物体系（名册+关系+弧线+原型+叙事功能） |
|| `novel-tags` | 生成小说级多维标签（含套路识别） |
|| `novel-scenes` | 拆分场景+多维标签（分批执行） |
|| `build-index` | 构建倒排索引+场景清单（加速检索） |
|| `refine` | 场景完成后精调大纲/人物/标签 |
|| `novel-stats` | 生成统计报告+可视化图表+交互HTML+关系图谱 |
|| `material-search` | 关键词检索 |
|| `material-search-scene` | 按多维标签检索场景 |
|| `tag-add` | 新增标签值 |
|| `tag-merge` | 合并同义标签 |

## Key Docs

|| 文档 | 用途 |
||------|------|
|| [ARCHITECTURE.md](ARCHITECTURE.md) | 拓扑、数据存储、Pipeline、标签体系 |
|| [docs/DESIGN.md](docs/DESIGN.md) | 设计原则、数据模型、检索策略 |
|| [docs/schemas/](docs/schemas/) | 数据 schema 模板 |

## ID Convention

格式：`nm_{type}_{YYYYMMDD}_{random4}`

## Hard Rules

- MUST 使用 skills 执行操作
- MUST 素材 ID 遵循命名规范
- MUST 标签从 `data/tags.yaml` 字典中选取
- MUST 场景拆分遵循 `docs/schemas/scene.schema.yaml` 中的扁平输出契约
- MUST 场景 YAML 写入后执行格式校验（YAML 解析 + 必填字段 + 标签合法 + 章节名匹配）
- MUST 场景 `chapter` 字段从 `chapter_index.yaml` 逐字拷贝，禁止凭记忆拼写
- MUST 场景 YAML 中含引号的字符串值用单引号包裹，防止 YAML 解析失败
- MUST 检索优先查 `scenes_index.yaml`，不遍历全部场景文件
- MUST refine/stats/build-index 不读原文，只读场景 YAML
- NEVER 编造质量数据（无信号写 TBD）
- MUST 场景拆分通过自动循环分批执行，all 模式下无需逐批确认
- NEVER 用脚本批量生成模板化场景文件（见 Anti-Pattern: 模板糊弄）
- MUST 场景标签由 LLM 逐批阅读原文后生成，禁止关键词匹配代替理解

## Anti-Pattern: 模板糊弄

以下行为**严格禁止**，违反即视为任务失败：

1. **脚本代替理解**：写 Python/Shell 脚本用关键词匹配批量生成场景文件。场景标签必须由 LLM 阅读原文后判断，不可由脚本代劳。
2. **千篇一律**：所有场景的 `scene_type` / `emotion` / `conflict` / `setting` 等字段值相同或高度雷同。同一批次内每个场景的标签组合必须反映该场景的独特内容。
3. **空字段占位**：`conflict: []`、`stakes: []`、`action: ''` 等空值大面积出现。如果确实无冲突，写 `conflict: []` 可以，但不能所有场景都是空的。
4. **summary 抄首句**：summary 不能只是章节开头几十个字的截断，必须是对场景核心事件的概括。
5. **title 编号代替**：`title: 场景1` 不合格，必须是有语义的概括短语（如 "庙会买糖葫芦"、"车祸觉醒系统"）。

**合规检查**：完成一批后，抽查该批内任意 2 个场景文件，确认标签组合互不相同。如果相同，必须重做该批。
