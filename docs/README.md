# 项目文档

本目录是 Novel Material V3 的项目文档入口。文档分为事实源、当前工作、历史归档和非项目文档四类；历史归档只用于追溯，不参与当前需求、架构或操作规范裁决。

## 事实源

| 文档 | 维护状态 | 用途 |
|---|---|---|
| [README](../README.md) | 现行入口 | 项目简介、当前能力与快速开始 |
| [项目需求](REQUIREMENTS.md) | 产品事实源 | 产品边界、质量目标、规模与不做什么 |
| [系统架构](../ARCHITECTURE.md) | 技术事实源 | 当前架构、数据流、模块边界与已知限制 |
| [用户手册](USER_MANUAL.md) | 使用事实源 | 与真实 CLI 一致的安装、命令和故障排查 |
| [Agent 指南](../AGENTS.md) | Agent 规则 | Codex 与通用 Agent 的项目操作规范 |
| [Claude 指南](../CLAUDE.md) | Agent 规则 | Claude Code 的项目操作规范 |

文档发生冲突时，依次以用户当前请求、Agent 指南、项目需求、系统架构、用户手册、README 为准。归档文档仅供追溯，不参与裁决。

## 当前工作

| 文档 | 维护状态 | 用途 |
|---|---|---|
| [检索容量与质量门禁](search-benchmark.md) | 当前实验状态 | 容量计划、ANN 准入条件与未执行项 |
| [未解决反馈](feedback.md) | 当前待办池 | 仍需处理的问题和想法 |
| [当前计划](current/plans/) | 当前计划 | 仍在执行或即将执行的计划 |

运行报告、前置导航、人物完整小传、分层世界观和作品画像能够说明流水线是否完整、资源消耗、产物规则问题和作品级结构入口，并让素材结构更完整，但不能替代检索质量评测。Golden Query 人工标注缺口仍然有效。

## 历史归档

| 目录 | 用途 |
|---|---|
| [归档说明](archive/README.md) | 归档区入口和历史链接说明 |
| [审查报告](archive/reviews/) | 历史代码审查和定向审查报告 |
| [事故复盘](archive/analysis/) | 事故分析和 postmortem |
| [已解决反馈](archive/feedback/) | 已完成反馈的历史记录 |
| [Superpowers 记录](archive/superpowers/) | 已完成或历史化的设计规格、实施计划和执行记录 |

归档文档默认不维护。历史计划、规格或执行记录与当前代码冲突时，以事实源文档和代码为准。

## 子系统契约

- [标签体系](../data/tag-system/README.md)：标签分类、维度和平台映射。
- [数据库迁移](../src/novel_material/storage/migrations/README.md)：已有数据库迁移顺序。

## 非项目文档

以下路径不纳入项目文档维护体系：

- `material/`：小说素材和语料。
- `data/`：运行数据、事实产物和可重建查询数据。
- `.pytest_cache/`：测试工具缓存。
- `*.egg-info/`：构建元数据。

## Skills

项目 Skills 以 `.agents/skills/` 为事实来源，`.claude/skills/` 为生成镜像；运行 `python scripts/sync_agent_skills.py --check` 可检查漂移。

## 建议阅读顺序

- 普通使用者：README -> 用户手册。
- 开发者：项目需求 -> 系统架构 -> 用户手册。
- Agent：AGENTS 或 CLAUDE -> 项目需求 -> 用户手册。
