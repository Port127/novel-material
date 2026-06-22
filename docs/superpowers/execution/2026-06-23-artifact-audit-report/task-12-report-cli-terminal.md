# Packet 12：report CLI 与终端摘要

**目标：** 实现只读报告重建命令和稳定终端摘要。

**详细步骤来源：** 完整计划 `Task 8` 的 Step 6–9。

```bash
sed -n '/^### Task 8：/,/^### Task 9：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `cli/pipeline.py`、`terminal/reporter.py` 及 CLI/terminal 测试。

**完成验证：** `python -m pytest tests/cli/test_pipeline_contract.py tests/terminal tests/reporting -v`。

**提交：** `feat(pipeline): 增加报告重建与终端摘要`。

**完成后：** 更新 STATE 指向 `task-13-docs-guards.md`。
