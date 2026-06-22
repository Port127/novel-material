# Packet 08：报告模型与事件构建器

**目标：** 从事件构建稳定的运行、阶段、质量、预算和同素材基线报告。

**详细步骤来源：** 完整计划 `Task 6`。

```bash
sed -n '/^### Task 6：/,/^### Task 7：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `reporting/{__init__,models,builder}.py`、`tests/reporting/test_builder.py`。

**完成验证：** `python -m pytest tests/reporting/test_builder.py tests/runtime/test_runtime_summary.py -v`。

**提交：** `feat(report): 建立运行与产物质量报告模型`。

**完成后：** 更新 STATE 指向 `task-09-report-writer.md`。
