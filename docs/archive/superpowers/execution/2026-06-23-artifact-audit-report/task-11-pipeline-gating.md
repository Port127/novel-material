# Packet 11：流水线审计门禁与 runtime wiring

**目标：** 将 audit 放在 sync 前，接入 JSONL/Report sinks，并保留 full 顶层降级诊断。

**详细步骤来源：** 完整计划 `Task 8` 的 Step 1–5。

```bash
sed -n '/^### Task 8：/,/^### Task 9：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `cli/pipeline_common.py`、`pipeline/orchestrator.py` 及 pipeline 测试。

**完成验证：** blocker 不执行 sync；ReportSink 失败后 full 仍为 degraded；相关 pipeline 测试全部通过。

**提交：** `feat(pipeline): 接入审计门禁与报告运行时`。

**完成后：** 更新 STATE 指向 `task-12-report-cli-terminal.md`。
