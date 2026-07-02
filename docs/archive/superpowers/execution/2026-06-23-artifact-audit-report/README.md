# 产物审计与运行报告：可恢复执行索引

## 每次新会话只读取

1. 仓库根目录 `AGENTS.md`。
2. 本目录 `STATE.md`。
3. `STATE.md` 指向的唯一 task 文件。
4. `git status --short` 与 `git log -3 --oneline`。

除非 task 文件明确要求，不读取完整对话、完整设计或 1440 行实施计划。

## 权威来源

- 总体设计：`docs/superpowers/specs/2026-06-23-layered-analysis-and-quality-report-design.md`
- 第一期完整技术计划：`docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md`
- 当前执行状态：本目录 `STATE.md`

## 执行规则

- 使用专用分支/worktree；首次执行时用 `using-git-worktrees` 建立。
- 一次会话默认只完成一个 packet；剩余额度充足时最多完成两个。
- 每个 packet 必须经过失败测试、最小实现、通过测试、独立提交和 STATE 更新。
- 未通过测试不得把 packet 标为完成。
- 被限额打断时保留工作区，不创建虚假的“完成”提交；下一会话先检查 diff。
- 不修改用户现有 `docs/feedback.md`。

## Packet 顺序

| Packet | 内容 | 依赖 |
|---|---|---|
| 01 | 审计模型契约 | 无 |
| 02 | 核心文件与章节覆盖规则 | 01 |
| 03 | 人物、世界观与 insights 规则 | 02 |
| 04 | 审计服务、阶段结果与规则 CLI | 03 |
| 05 | 复审预算与 reviewer | 04 |
| 06 | dispatcher 上下文与 LLM telemetry | 05 |
| 07 | orchestrator 事件、异常与审计事件 | 06 |
| 08 | 报告模型与事件构建器 | 07 |
| 09 | Markdown 与原子 writer | 08 |
| 10 | ReportSink 与 JSONL reader | 09 |
| 11 | audit/sync 门禁与 runtime wiring | 10 |
| 12 | report CLI 与终端摘要 | 11 |
| 13 | 依赖护栏与权威文档 | 12 |
| 14 | 全量验证与真实只读验收 | 13 |

第二期和第三期不在本执行包中。第一期通过完成门禁后，分别依据总体设计创建新的执行包。
