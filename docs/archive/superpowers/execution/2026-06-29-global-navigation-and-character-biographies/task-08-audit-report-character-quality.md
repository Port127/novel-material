# Packet 08：审计与报告人物小传质量信号

**目标：** 审计完整小传目标缺失、伪完成和简档边界，并在报告展示人物小传质量汇总。

**详细步骤来源：** 完整计划 `Task 8`。

```bash
sed -n '/^## Task 8：更新审计与报告的人物小传质量信号/,/^## Task 9：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/audit/test_rules.py tests/reporting/test_builder.py tests/reporting/test_markdown.py tests/terminal/test_terminal_core.py -v
```

**提交：** `feat(audit): 增加人物小传质量信号`
