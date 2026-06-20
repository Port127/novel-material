# 项目文档整理设计

## 目标

重新梳理项目文档，使现行文档准确描述当前代码和已经确认的产品方向；删除已经失效或完成使命的参考文档，避免历史方案与现行规范相互冲突。

## 文档必须遵守的产品决策

- Novel Material 是小说写作参考检索库，不在项目内部负责小说内容生成。
- 本项目负责检索和结构化展示；外部 Agent 负责理解、糅合和生成。
- 检索质量是第一目标。深度检索允许最长约三分钟的响应时间。
- 现有 4096 维向量保留为质量基线。降维不是既定要求，只有经过质量对比后才能考虑。
- 长期容量目标为 500～5000 本小说；按每本约 500 章估算，对应约 25 万～250 万章。
- 章节仍是最小分析单元，不拆分事件和场景。

## 文档职责与单一事实来源

| 文档 | 职责 |
|---|---|
| `README.md` | 项目入口、当前能力、快速开始和文档导航 |
| `docs/REQUIREMENTS.md` | 产品边界、优先级、规模、质量目标和明确不做的内容 |
| `ARCHITECTURE.md` | 当前已经实现的架构、数据流、模块边界和已知限制 |
| `docs/USER_MANUAL.md` | 与实际 CLI 一致的命令和操作方法 |
| `AGENTS.md` | 通用 Agent 与 Codex 的项目操作规则 |
| `CLAUDE.md` | Claude Code 操作规则；除平台专属路径外与 `AGENTS.md` 同步 |
| `docs/GENRE_AWARE_ANALYSIS.md` | 已实现的题材感知深度分析功能说明 |
| `docs/README.md` | 文档索引、状态、权威性和建议阅读顺序 |

文档内容发生冲突时，按以下顺序判断：

1. 产品决策以 `docs/REQUIREMENTS.md` 为准。
2. 技术实现以 `ARCHITECTURE.md` 为准。
3. 使用方法以 `docs/USER_MANUAL.md` 为准。
4. Agent 行为以 `AGENTS.md` 或 `CLAUDE.md` 为准。
5. `README.md` 只对上述文档做简明概括。

## 文件处置方案

### 新增

- `docs/README.md`
  - 建立统一文档入口。
  - 将保留文档标记为现行规范、现行指南、待办反馈、历史归档、执行计划或子系统契约。

### 更新

- `README.md`
  - 保持简洁，面向第一次接触项目的使用者。
  - 在功能概览中加入题材感知深度分析。
  - 修正路径和环境要求。
  - 链接到 `docs/README.md`，不再重复大段细节。
- `docs/REQUIREMENTS.md`
  - 将统一的“两秒响应”要求改为质量优先。
  - 记录深度检索最长约三分钟的可接受响应时间。
  - 将规划容量更新为 500～5000 本小说。
  - 将 4096 维向量保留为当前质量基线，不预设必须降维。
  - 将质量指标和未来性能优化决策分开描述。
- `ARCHITECTURE.md`
  - 补充已经实现的题材感知分析模块和产物。
  - 如实描述现有检索层：4096 维精确向量检索、关键词 `ILIKE` 查询、没有 ANN 索引，以及内部搜索模块与 CLI 暴露命令的区别。
  - 不把计划中的混合检索描述成已经实现。
- `docs/USER_MANUAL.md`
  - 根据 `nm --help` 和各子命令的帮助信息重新核对命令清单。
  - 删除文档中存在、但 CLI 没有注册的命令：`nm search event`、`nm storage sync-all`、`nm storage reset`、`nm validate schema`、`nm validate all`。
  - 如实记录已经实现的 `nm pipeline insights`、`nm search insight` 和 `nm validate insights`。
  - 将 Python 要求修正为 3.10 及以上。
  - 增加“当前已知限制”，避免把现有检索描述成完整的混合检索或默认语义检索。
- `AGENTS.md` 与 `CLAUDE.md`
  - 同步公共规则和命令清单。
  - 只保留 Agent 名称和 Skill 目录的平台差异。
  - 将 Codex Skill 路径修正为 `.agents/skills/`。
  - 删除“当前 `nm search chapter` 默认使用语义检索”的错误表述。
  - 不再硬编码当前模型名称，以配置文件作为实际模型来源。
  - 补充已经实现的 insights 阶段，但不把它写成所有运行模式的强制步骤。
- `docs/GENRE_AWARE_ANALYSIS.md`
  - 纳入正式文档导航。
  - 用模型能力描述替代固定模型名称，并指向 `config/providers.yaml` 查询当前服务商。
- `docs/feedback.md`
  - 只保留尚未解决的反馈。
  - 文档整理完成并验证后，移除已经完成的文档整理事项。
- `src/novel_material/storage/migrations/README.md`
  - 在执行顺序和迁移历史中完整记录现有两个迁移文件。

### 删除

- `docs/CLAUDE_CODE_SETTINGS.md`
  - 这是通用 Claude Code 配置参考，与 Novel Material 的业务和运行方式无关，也没有项目内链接指向它。
- `docs/classify_implementation.md`
  - 分类功能已经实现；当前行为应由架构文档和用户手册说明，不再保留旧实施方案。
- `docs/superpowers/plans/2026-06-16-genre-aware-analysis-profiles.md`
  - 计划已经执行完成，现有代码和 `docs/GENRE_AWARE_ANALYSIS.md` 已取代它。
- `docs/superpowers/plans/2026-06-20-word-count-contract-fix.md`
  - 任务已经完成，测试和 Git 历史足以记录结果。
- `docs/superpowers/specs/2026-06-20-word-count-contract-design.md`
  - 一次性设计已经完成，当前字数契约和测试已取代它。
- `docs/code-review-report.md`
  - 保留当前删除状态，不恢复该文件。已确认的问题将进入现行文档或后续检索实施计划。

### 保留但不重写

- `docs/feedback/archive/*.md`
  - 属于历史项目记忆，并被反馈归档工作流使用。
- `data/tag-system/*.md`
  - 属于标签子系统契约，不纳入本次通用文档重写。
- `.agents/skills/*/SKILL.md` 与 `.claude/skills/*/SKILL.md`
  - 本次只修正文档对 Skills 的引用，不改变 Skill 行为。

## 验证标准

只有满足以下条件，文档整理才算完成：

1. `python -m pytest -q` 仍然得到 `73 passed, 1 skipped`；如果并行改动改变了测试数量，则必须得到更新后的全绿基线。
2. `docs/USER_MANUAL.md`、`AGENTS.md` 和 `CLAUDE.md` 的命令清单与以下输出一致：
   - `nm --help`
   - `nm pipeline --help`
   - `nm search --help`
   - `nm tags --help`
   - `nm material --help`
   - `nm storage --help`
   - `nm validate --help`
3. 所有保留的现行文档中，相对 Markdown 链接都能指向存在的文件。
4. 现行文档中不再出现以下过时表述：
   - 支持 Python 3.8。
   - 所有检索必须在两秒内返回。
   - `nm search event` 是已经暴露的命令。
   - `nm storage sync-all` 或 `nm storage reset` 是已经暴露的命令。
   - `nm validate schema` 或 `nm validate all` 是已经暴露的命令。
   - 当前章节检索默认使用语义检索。
5. `AGENTS.md` 与 `CLAUDE.md` 只存在 Agent 名称和 Skill 路径两处平台差异。
6. 不触碰现有的 `config/providers.yaml` 未提交修改。

## 本次不做

- 不在本轮实施检索功能改造。
- 不修改数据库结构，不迁移向量。
- 不恢复 `docs/code-review-report.md`。
- 不重写反馈归档和标签子系统契约。
- 不把计划中的质量改进描述成已经实现的能力。
