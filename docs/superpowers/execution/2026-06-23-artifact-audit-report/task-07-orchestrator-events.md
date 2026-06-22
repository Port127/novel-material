# Packet 07：orchestrator 与审计事件

**目标：** 发布完整阶段事件、转换未处理异常，并发布 `ArtifactAuditCompleted`。

**详细步骤来源：** 完整计划 `Task 5` 的 Step 2、5、7–9。

```bash
sed -n '/^### Task 5：/,/^### Task 6：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `pipeline/{orchestrator,stages}.py`、`runtime/context.py` 及 pipeline 测试。

**完成验证：** `python -m pytest tests/pipeline/test_orchestrator.py tests/runtime -v`。

**提交：** `feat(runtime): 补齐阶段与审计完成事件`。

**完成后：** 更新 STATE 指向 `task-08-report-builder.md`。
