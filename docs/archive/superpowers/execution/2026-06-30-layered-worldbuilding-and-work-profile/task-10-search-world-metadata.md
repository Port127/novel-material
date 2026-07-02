# Packet 10：`search world` 适配新实体 metadata

**目标：** `search world` 返回 `entity_id`、`dimension_ids`、`evidence` 和 `relation_summaries`，同时保持旧过滤别名兼容。

**详细步骤来源：** 完整计划 Task 10。

**关键文件：**

- `src/novel_material/search/world.py`
- `src/novel_material/cli/search.py`
- `tests/search/test_retrievers.py`
- `tests/search/test_contracts.py`
- `tests/cli/test_command_contracts.py`

**完成验证：**

```bash
python -m pytest tests/search/test_retrievers.py tests/search/test_contracts.py tests/cli/test_command_contracts.py -v
python -m novel_material.cli.main search world --help
python -m compileall -q src/novel_material/search src/novel_material/cli
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-11-docs-final-verification.md`。

**提交：** `feat(search): 适配分层世界观检索元数据`
