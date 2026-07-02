# Packet 03：人物、世界观与 insights 规则

**目标：** 补齐人物兜底、世界观空结构、finalized 产物和 insight 覆盖规则并注册 RULES。

**详细步骤来源：** 完整计划 `Task 2`，从 `check_character_profiles` 起读取到 Task 3 前。

```bash
sed -n '/3\. `check_character_profiles`/,/^### Task 3：/p' docs/superpowers/plans/2026-06-23-artifact-audit-and-run-report.md
```

**文件：** `src/novel_material/audit/rules.py`、`tests/audit/test_rules.py`。

**完成验证：** `python -m pytest tests/audit/test_rules.py -v`，预期全部通过。

**提交：** `feat(audit): 增加人物与世界观质量规则`。

**完成后：** 更新 STATE 指向 `task-04-audit-service-cli.md`。
