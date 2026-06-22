# Packet 02：核心文件与章节覆盖规则

**目标：** 实现 `AuditContext`、问题工厂、必需文件检查和章节覆盖检查。

**详细步骤来源：** 完整计划 `Task 2` 的 Step 1–4；本 packet 只实现 `check_required_files` 与 `check_chapter_coverage`。

```bash
sed -n '/^### Task 2：/,/^### Task 3：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `src/novel_material/audit/rules.py`、`tests/audit/test_rules.py`。

**完成验证：** 运行必需文件和覆盖率两个定向测试；预期通过，其他尚未实现规则不得注册。

**提交：** `feat(audit): 检查核心文件与章节覆盖`。

**完成后：** 更新 STATE 指向 `task-03-domain-rules.md`。
