# Packet 6：世界观审计与报告质量信号

**目标：** 审计 layered 世界观的适用维度、实体证据和关系引用，并在报告中展示质量摘要。

**详细步骤来源：** 完整计划 Task 6。

**关键文件：**

- `src/novel_material/audit/rules.py`
- `src/novel_material/audit/service.py`
- `src/novel_material/reporting/models.py`
- `src/novel_material/reporting/builder.py`
- `src/novel_material/reporting/markdown.py`
- `tests/audit/`
- `tests/reporting/`

**完成验证：**

```bash
python -m pytest tests/audit tests/reporting -v
python -m compileall -q src/novel_material/audit src/novel_material/reporting
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-07-work-profile-contract.md`。

**提交：** `feat(audit): 增加分层世界观质量信号`
