# Novel Material V3 文档收敛设计

## 目标

将项目正式升级为 Novel Material V3，并以当前代码、CLI 和数据契约为依据重建现行文档边界。V3 文档必须准确描述已实现能力、明确未完成质量验收，不再保留重复或过期的 V2 功能说明。

## 版本边界

- `pyproject.toml` 的包版本从 `2.0.0` 升级为 `3.0.0`。
- 现行入口文档和代码注释中的项目代际统一为 V3。
- 数据文件自身的 `schema_version`、数据库迁移版本和 embedding provenance 版本不随包版本机械修改；它们有独立兼容语义。
- 历史 specs、plans、feedback archive 保留原始版本表述，不做追溯性改写。

## 权威文档职责

### `README.md`

面向首次接触项目的人，只保留：V3 定位、核心原则、当前能力、快速开始、运行模式和文档导航。当前能力必须覆盖七类质量优先检索，删除“章节仍是单路关键词搜索”等过期描述。

### `docs/REQUIREMENTS.md`

作为产品事实来源，只记录用户场景、检索需求、质量目标、规模、边界和明确不做的内容。实现细节只保留能约束产品决策的原则，不重复模块和命令说明。

### `ARCHITECTURE.md`

作为技术事实来源，记录当前目录、契约、流水线、L1/L2 分析、存储、三路检索、RRF、重排、上下文、降级和已知限制。不得把规划中或待评测能力描述成已验证事实。

### `docs/USER_MANUAL.md`

作为操作事实来源，以真实 `--help` 为准，覆盖安装、配置、pipeline、七类 search、eval、storage migrate、validate、故障排查和高风险副作用。

### `AGENTS.md` 与 `CLAUDE.md`

`AGENTS.md` 是共享 Agent 规则事实来源。`CLAUDE.md` 同步相同正文，只允许 Skill 目录入口等宿主差异。搜索能力、命令、禁止事项和风险提示必须一致。

### `docs/README.md`

只维护现行文档索引、工作记录边界和明确待办。删除失效链接，并说明历史 specs/plans 不是当前功能事实来源。

## 题材感知分析文档处置

`docs/GENRE_AWARE_ANALYSIS.md` 描述的功能仍存在，不能直接丢失，但没有必要继续作为独立现行文档维护：

- profile 组合、L1/L2 分层、输出路径和数据流并入 `ARCHITECTURE.md`。
- CLI、运行模式、配置和校验方式并入 `docs/USER_MANUAL.md`。
- 扩展 profile 的开发约束并入架构中的 analysis profiles 小节。
- 合并完成并验证无独有事实丢失后，删除 `docs/GENRE_AWARE_ANALYSIS.md` 及所有现行入口链接。

## Skills 同步关系

本工作同时实施已批准的 `2026-06-22-agent-claude-skills-sync-design.md`：

- `.agents/skills` 是事实来源。
- 平台差异改为平台中立正文。
- `.claude/skills` 由同步工具生成并用 `--check` 校验。
- 文档一致性检查同时验证 `AGENTS.md / CLAUDE.md` 和两个 Skills 目录。

## 一致性检查

新增确定性检查，至少覆盖：

- 现行文档不得出现 `Novel Material V2` 或包版本 `2.0.0`。
- 文档声明的公开 CLI 子命令必须在 Typer 帮助中存在。
- 被删除文档不得残留现行链接。
- `AGENTS.md` 与 `CLAUDE.md` 在规范化宿主路径后内容一致。
- 两个 Skills 目录的受管文件集合和内容哈希一致。
- Golden Query、三档容量实测、LLM 重排效果仍未完成时，文档必须保留相应限制声明。

## 实施顺序

1. 建立失败的一致性测试，锁定 V2、过期 CLI、重复 Skill 和失效链接。
2. 正式升级包版本。
3. 平台中立化并同步 Skills。
4. 更新 README、需求、架构、手册和 Agent 规则。
5. 合并并删除题材感知独立文档。
6. 运行 CLI 帮助、链接检查、文档一致性测试和全量单测。

## 不做的内容

- 不改写历史 specs、plans 和反馈归档。
- 不因 V3 名称重置 YAML schema、数据库迁移或 embedding 文件。
- 不补写人工相关性标签，不伪造质量基线或容量实测。
- 不在文档整理中修复或重新分析已有素材。

## 验收标准

- 包版本和所有现行入口统一为 V3。
- 上述权威文档职责清晰且无关键事实冲突。
- `GENRE_AWARE_ANALYSIS.md` 的有效内容已合并，文件和链接已删除。
- `AGENTS.md / CLAUDE.md`、`.agents/skills / .claude/skills` 通过同步校验。
- CLI 文档与真实帮助一致，全部自动检查和现有测试通过。
- 用户的 `docs/feedback.md` 与本地 `eval/search_candidates.yaml` 不被覆盖或纳入提交。
