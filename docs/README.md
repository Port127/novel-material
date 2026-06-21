# 项目文档

本目录只保留与当前项目直接相关的现行文档、工作记录和历史反馈。产品边界、技术实现和使用方式分别由不同文档负责，避免同一信息在多处重复维护。

## 现行文档

| 文档 | 状态 | 用途 |
|---|---|---|
| [README](../README.md) | 现行入口 | 项目简介、当前能力与快速开始 |
| [项目需求](REQUIREMENTS.md) | 产品事实来源 | 产品边界、质量目标、规模与不做什么 |
| [系统架构](../ARCHITECTURE.md) | 技术事实来源 | 当前架构、数据流、模块边界与已知限制 |
| [用户手册](USER_MANUAL.md) | 使用事实来源 | 与真实 CLI 一致的安装和操作方法 |
| [Agent 指南](../AGENTS.md) | Agent 规则 | Codex 与通用 Agent 的项目操作规范 |
| [Claude 指南](../CLAUDE.md) | Agent 规则 | Claude Code 的项目操作规范 |
| [检索容量与质量门禁](search-benchmark.md) | 实验状态 | 容量计划、ANN 准入条件与未执行项 |

文档发生冲突时，依次以项目需求、系统架构、用户手册、Agent 指南为准。README 只做摘要，不覆盖详细规范。

## 工作记录

- [未解决反馈](feedback.md)：仍需处理的问题和想法。
- [反馈归档](feedback/archive/)：已解决问题的历史记录，只用于追溯。
- [设计规格](superpowers/specs/)：当前仍有参考价值的设计决策。
- [实施计划](superpowers/plans/)：当前正在执行的任务计划。

工作记录不属于现行功能说明。历史计划与当前代码冲突时，以现行文档和代码为准。

## 待办与已知缺口

### 检索 Golden Query 人工标注

- `eval/search_queries.yaml` 已包含 30 条真实业务查询，候选准备和标签导入命令已经实现。
- `eval/search_candidates.yaml` 是本地人工标注工作文件，当前标注尚未完成，不纳入版本控制；不得由 Agent 猜测或自动填写 `relevance`。
- 人工标注延期处理，因此暂未生成 `eval/baselines/4096-exact.json`。在基线补齐前，后续实现可以继续，但不得声称混合检索或重排质量已经达到、不低于或优于 4096 维精确基线。
- 恢复该待办时，应先保留已有人工填写内容，再完善候选证据和不确定项处理；禁止直接重新生成候选文件覆盖人工修改。
- 完成人工标注后，依次执行 `nm eval search import-labels` 和 `nm eval search score --mode exact`，再恢复依赖质量基线的门禁验收。
- 25 万、50 万和 250 万章容量实测随质量基线延期；当前只有安全计划入口和硬门禁，不得虚构结论。

## 子系统契约

- [标签体系](../data/tag-system/README.md)：标签分类、维度和平台映射。
- [数据库迁移](../src/novel_material/storage/migrations/README.md)：已有数据库迁移顺序。

## 建议阅读顺序

- 普通使用者：README → 用户手册。
- 开发者：项目需求 → 系统架构 → 用户手册。
- Agent：AGENTS 或 CLAUDE → 项目需求 → 用户手册。
