# Packet 04：审计服务、阶段结果与规则 CLI

**目标：** 完成问题去重排序、StageResult 适配和默认零 LLM 的 `nm validate artifacts`。

**详细步骤来源：** 完整计划 `Task 3`。

```bash
sed -n '/^### Task 3：/,/^### Task 4：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `audit/service.py`、`audit/__init__.py`、`pipeline/stages.py`、`cli/validate.py` 及对应测试。

**完成验证：** `python -m pytest tests/audit/test_service.py tests/cli/test_command_contracts.py tests/validation -v`。

**提交：** `feat(audit): 接入产物审计服务与命令`。

**完成后：** 更新 STATE 指向 `task-05-review-budget.md`。
