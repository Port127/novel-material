# Packet 05：预算受控的 LLM 复审

**目标：** 实现双重预算、reviewer 协议、受限证据和 `--review`，确保不写事实 YAML。

**详细步骤来源：** 完整计划 `Task 4`。

```bash
sed -n '/^### Task 4：/,/^### Task 5：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `audit/{budget,reviewer,service}.py`、`cli/validate.py`、`config/settings.yaml` 及测试。

**完成验证：** `python -m pytest tests/audit tests/cli/test_command_contracts.py -v`；测试不得联网。

**提交：** `feat(audit): 增加预算受控的可疑项复审`。

**完成后：** 更新 STATE 指向 `task-06-runtime-dispatcher.md`。
