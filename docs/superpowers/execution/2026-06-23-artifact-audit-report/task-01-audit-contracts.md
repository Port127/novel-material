# Packet 01：审计模型契约

**目标：** 建立 `AuditSeverity`、`ReviewState`、`ArtifactIssue`、`ReviewBudgetUsage`、`ArtifactAudit` 与状态映射。

**详细步骤来源：** 完整计划 `Task 1`。只读取该节：

```bash
sed -n '/^### Task 1：/,/^### Task 2：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `src/novel_material/audit/{__init__,models}.py`、`tests/audit/test_models.py`。

**完成验证：** `python -m pytest tests/audit/test_models.py -v`，预期全部通过。

**提交：** `feat(audit): 建立产物审计结果契约`，正文记录主要改动与验证结果。

**完成后：** 更新 STATE 指向 `task-02-core-rules.md`。
