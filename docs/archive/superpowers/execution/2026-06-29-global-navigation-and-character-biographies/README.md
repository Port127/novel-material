# 前置导航与人物小传：可恢复执行索引

## 每次新会话只读取

1. 仓库根目录 `AGENTS.md`。
2. 本目录 `STATE.md`。
3. `STATE.md` 指向的唯一 task 文件。
4. `git status --short` 与 `git log -3 --oneline`。

除非 task 文件明确要求，不读取完整对话、完整总体设计或完整实施计划。

## 权威来源

- 总体设计：`docs/superpowers/specs/2026-06-23-layered-analysis-and-quality-report-design.md`
- 第二期完整技术计划：`docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md`
- 当前执行状态：本目录 `STATE.md`

## 执行规则

- 当前用户已明确要求在当前分支执行；不要自行创建新分支或 worktree。
- 一次会话默认只完成一个 packet；剩余额度充足时最多完成两个。
- 每个 packet 必须经过失败测试、最小实现、通过测试、独立提交和 STATE 更新。
- 未通过测试不得把 packet 标为完成。
- 被限额打断时保留工作区，不创建虚假的“完成”提交；下一会话先检查 diff。
- 不修改用户现有 `docs/feedback.md`。
- 不调用真实 LLM，除非 packet 明确要求并且用户单独授权。

## Packet 顺序

| Packet | 内容 | 依赖 |
|---|---|---|
| 01 | evaluation 3.0.0 模型与旧版适配器 | 无 |
| 02 | evaluate 写入前置导航 | 01 |
| 03 | `--window` 与前置导航解耦 | 02 |
| 04 | 自适应人物选择器 | 01 |
| 05 | 完整小传契约与 prompt | 04 |
| 06 | characters 阶段接入小传与简档 | 05 |
| 07 | 定向人物修复 CLI | 06 |
| 08 | 审计与报告人物小传质量信号 | 06 |
| 09 | continue/status 阶段契约 | 03、08 |
| 10 | 性能预算与真实只读 smoke | 09 |
| 11 | 文档、help 与完成门禁 | 10 |

第三期“分层世界观与作品画像”不在本执行包中。
