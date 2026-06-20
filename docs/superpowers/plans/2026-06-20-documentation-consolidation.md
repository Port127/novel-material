# 项目文档整理实施计划

> **供执行 Agent 使用：** 必须使用 `executing-plans` 逐项执行本计划，并用复选框记录进度。

**目标：** 建立清晰、准确、以中文为主的项目文档体系，使产品边界、真实架构、CLI 使用方法和 Agent 规则彼此一致，并删除已经失效的文档。

**架构：** 以 `docs/REQUIREMENTS.md`、`ARCHITECTURE.md`、`docs/USER_MANUAL.md`、`AGENTS.md`/`CLAUDE.md` 为四层事实来源，`README.md` 只做入口摘要，新增 `docs/README.md` 统一标注文档状态。历史反馈归档与标签契约保留，已完成的一次性方案和无关参考文档删除。

**技术栈：** Markdown、Typer CLI 帮助信息、Git、pytest

---

### 任务 1：建立文档索引并清理失效文件

**文件：**
- 新建：`docs/README.md`
- 删除：`docs/CLAUDE_CODE_SETTINGS.md`
- 删除：`docs/classify_implementation.md`
- 删除：`docs/superpowers/plans/2026-06-16-genre-aware-analysis-profiles.md`
- 删除：`docs/superpowers/plans/2026-06-20-word-count-contract-fix.md`
- 删除：`docs/superpowers/specs/2026-06-20-word-count-contract-design.md`
- 保持删除：`docs/code-review-report.md`

- [x] **步骤 1：新建统一文档索引**

`docs/README.md` 必须包含以下分类和状态：

```markdown
# 项目文档

## 现行文档

| 文档 | 状态 | 用途 |
|---|---|---|
| `../README.md` | 现行入口 | 项目简介与快速开始 |
| `REQUIREMENTS.md` | 产品事实来源 | 边界、目标与不做什么 |
| `../ARCHITECTURE.md` | 技术事实来源 | 当前架构与已知限制 |
| `USER_MANUAL.md` | 使用事实来源 | 与 CLI 一致的操作手册 |
| `../AGENTS.md` | Agent 规则 | Codex/通用 Agent 操作规范 |
| `../CLAUDE.md` | Agent 规则 | Claude Code 操作规范 |
| `GENRE_AWARE_ANALYSIS.md` | 功能指南 | 题材感知深度分析 |

## 工作记录

- `feedback.md`：未解决反馈。
- `feedback/archive/`：历史反馈归档，只用于追溯。
- `superpowers/specs/`：当前设计规格。
- `superpowers/plans/`：当前执行计划。

## 子系统契约

- `../data/tag-system/README.md`：标签体系入口。
- `../src/novel_material/storage/migrations/README.md`：数据库迁移说明。

## 阅读顺序

普通使用者：README → USER_MANUAL。
开发者：REQUIREMENTS → ARCHITECTURE → USER_MANUAL。
Agent：AGENTS 或 CLAUDE → REQUIREMENTS → USER_MANUAL。
```

- [x] **步骤 2：删除规格中确认失效的文件**

使用 `apply_patch` 删除上述五个仍存在的文件；不恢复已经删除的 `docs/code-review-report.md`。

- [x] **步骤 3：核对清理结果**

运行：

```bash
rg --files docs | sort
```

预期：现行文档、反馈归档、当前文档整理规格和计划仍存在；已列入删除清单的文件不存在。

### 任务 2：更新产品需求与质量目标

**文件：**
- 修改：`docs/REQUIREMENTS.md`

- [x] **步骤 1：修正产品定位与职责边界**

保留“项目负责检索与展示，Agent 负责理解、糅合和生成”，并明确本项目不是内部生成系统，也不拆分场景和事件。

- [x] **步骤 2：更新规模与响应目标**

将规模目标改为：

```markdown
| 小说数量 | 500～5000 本 |
| 每本章节 | 约 500 章 |
| 总章节数 | 约 25 万～250 万章 |
| 深度检索响应 | 质量优先，最长约 3 分钟 |
| 并发检索 | 支持多个 Agent 调用，性能优化不得突破质量下限 |
```

删除“所有检索必须小于 2 秒”的硬性要求。

- [x] **步骤 3：加入向量质量原则**

明确现有 4096 维向量是当前质量基线；降维、近似索引和独立向量数据库只能在基准评测证明质量无明显损失后采用。

- [x] **步骤 4：检查需求文档内部一致性**

运行：

```bash
rg -n "2 秒|< 2|1000 本起步|50 万章|4096|三分钟|250 万" docs/REQUIREMENTS.md
```

预期：只保留新的质量优先、500～5000 本和 25 万～250 万章口径。

### 任务 3：重写项目入口与 Agent 指南

**文件：**
- 修改：`README.md`
- 修改：`AGENTS.md`
- 修改：`CLAUDE.md`

- [x] **步骤 1：收敛 README**

README 只保留：项目定位、核心原则、当前能力、快速开始、数据产物、测试和文档导航。加入 `nm pipeline insights`，并链接 `docs/README.md`。不得把 `nm search event` 写成已暴露命令，也不得描述尚未实现的混合检索。

- [x] **步骤 2：同步 Agent 公共规则**

两份 Agent 文档必须共同包含：

- CLI 优先于底层模块。
- YAML 是事实来源，PostgreSQL 是可重建查询层。
- 当前公开搜索命令只有 `outline`、`character`、`chapter`、`world`、`insight`。
- insights 是按模式启用的增强阶段，不是所有流水线的强制步骤。
- 当前模型从 `config/providers.yaml` 与配置服务读取，不在文档中固定为某个模型版本。
- 搜索结果质量优先，不擅自降维或修改数据库。

- [x] **步骤 3：保留两处平台差异**

`AGENTS.md` 使用“Codex/通用 Agent”和 `.agents/skills/`；`CLAUDE.md` 使用“Claude Code”和 `.claude/skills/`。除此之外保持一致。

- [x] **步骤 4：验证差异范围**

运行：

```bash
diff -u AGENTS.md CLAUDE.md
```

预期：只显示 Agent 名称和 Skill 路径差异。

### 任务 4：使架构文档反映当前代码

**文件：**
- 修改：`ARCHITECTURE.md`
- 参考：`src/novel_material/analysis_profiles/`
- 参考：`src/novel_material/pipeline/insights.py`
- 参考：`src/novel_material/search/insight.py`
- 参考：`src/novel_material/storage/schema.sql`
- 参考：`src/novel_material/search/*.py`

- [x] **步骤 1：更新目录结构和数据流**

加入 `analysis_profiles/`、`pipeline/insights.py`、`search/insight.py`、`validation/insights.py` 和 `eval/insights_eval.py`；在数据流中说明 `chapter_insights/` 是可选 L2 产物，不替代 `chapters.yaml`。

- [x] **步骤 2：如实说明检索现状**

写明：

- 章节、人物、世界观和大纲存在 4096 维向量列。
- 当前没有启用 ANN 向量索引，语义分支使用精确距离排序。
- 关键词分支使用 `ILIKE`，尚未实现中文全文索引。
- 当前关键词与向量是二选一，不是混合召回。
- `event.py` 与 `detail.py` 是内部模块，未注册到主 CLI。
- `insight` 搜索读取本地 YAML，不属于 PostgreSQL 向量检索。

- [x] **步骤 3：删除过时或超前描述**

不得把未来的混合检索、重排或性能优化写成当前能力；模型名称改为配置驱动。

### 任务 5：按真实 CLI 修订用户手册

**文件：**
- 修改：`docs/USER_MANUAL.md`

- [x] **步骤 1：修正环境和生命周期**

Python 改为 3.10+；数据状态、运行模式和 insights 产物与当前代码一致。

- [x] **步骤 2：修正命令章节**

根据 CLI 帮助保留：

```text
pipeline: ingest analyze insights evaluate outline worldbuilding characters tags refine full status continue
search: outline character chapter world insight
storage: init-db init-data init-tags sync
validate: validate quality insights
```

删除或改为“内部模块、不可从 `nm` 主 CLI 调用”：`search event`、`search detail`。删除 `storage sync-all/reset` 和 `validate schema/all` 的命令说明。

- [x] **步骤 3：增加检索已知限制**

明确当前章节搜索默认是关键词 `ILIKE`，主 CLI 未暴露语义开关；现有向量分支不是混合检索；后续质量改造另行规划。

- [x] **步骤 4：重建附录命令速查**

附录必须与步骤 2 的命令清单完全一致，不保留正文已删除的旧命令。

### 任务 6：整理专题说明、反馈和迁移文档

**文件：**
- 修改：`docs/GENRE_AWARE_ANALYSIS.md`
- 修改：`docs/feedback.md`
- 修改：`src/novel_material/storage/migrations/README.md`

- [x] **步骤 1：更新题材感知说明**

删除固定模型版本，改为“面向支持结构化输出和中等推理能力的模型”；指出当前模型由 `config/providers.yaml` 决定。

- [x] **步骤 2：清理已完成反馈**

删除 `docs/feedback.md` 中已经由本轮完成的文档检查与更新条目，保留其他未解决反馈。

- [x] **步骤 3：补全迁移说明**

执行顺序必须列出：

```text
001_add_key_event.sql
002_add_chapter_tags.sql
```

并说明新数据库直接执行 `nm storage init-db`，已有数据库按编号执行迁移。

### 任务 7：全量验证并提交

**文件：**
- 验证：所有保留的现行 Markdown 文档
- 保留：`config/providers.yaml` 未提交修改

- [x] **步骤 1：验证真实 CLI**

运行：

```bash
nm --help
nm pipeline --help
nm search --help
nm tags --help
nm material --help
nm storage --help
nm validate --help
```

预期：文档命令清单与输出一致。

- [x] **步骤 2：扫描过时表述**

运行：

```bash
rg -n "Python 3\.8|2 秒|< 2 秒|nm search event|nm storage sync-all|nm storage reset|nm validate schema|nm validate all|章节检索（向量语义）" README.md AGENTS.md CLAUDE.md ARCHITECTURE.md docs/README.md docs/REQUIREMENTS.md docs/USER_MANUAL.md docs/GENRE_AWARE_ANALYSIS.md
```

预期：无命中；如果在“未实现能力”说明中出现，必须人工确认语义明确。

- [x] **步骤 3：检查相对链接**

提取现行文档的相对 Markdown 链接，逐个确认目标文件存在；不得留下指向已删除文档的链接。

- [x] **步骤 4：运行测试**

运行：

```bash
python -m pytest -q
```

预期：`73 passed, 1 skipped`，或并行工作产生的更新后全绿基线。

- [x] **步骤 5：检查工作区边界**

运行：

```bash
git diff --check
git status --short
```

预期：文档整理改动与既有 `config/providers.yaml` 修改清楚分离，不出现业务代码修改。

- [x] **步骤 6：提交文档整理**

只暂存本计划涉及的文档，不暂存 `config/providers.yaml`：

```bash
git add README.md AGENTS.md CLAUDE.md ARCHITECTURE.md docs src/novel_material/storage/migrations/README.md
git commit -m "docs: consolidate project documentation"
```

预期：提交成功，`config/providers.yaml` 仍作为未提交修改保留。
