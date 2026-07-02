# Packet 11：文档、help 与完成门禁

**目标：** 更新权威文档、运行第二期最终验收，并将 STATE 标记为 complete。

**详细步骤来源：** 完整计划 `Task 11` 与“第二期完成门禁”。

```bash
sed -n '/^## Task 11：文档、CLI help 与完成门禁/,$p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/audit tests/reporting tests/runtime tests/run_logging tests/pipeline tests/terminal tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v
python -m novel_material.cli.main pipeline full --help
python -m novel_material.cli.main pipeline analyze --help
python -m novel_material.cli.main pipeline characters --help
python -m novel_material.cli.main validate artifacts --help
python -m compileall -q src/novel_material
python scripts/check_v3_docs.py
git diff --check -- . ':(exclude)docs/feedback.md'
git status --short
```

**提交：** `docs(characters): 完成前置导航与人物小传文档`
