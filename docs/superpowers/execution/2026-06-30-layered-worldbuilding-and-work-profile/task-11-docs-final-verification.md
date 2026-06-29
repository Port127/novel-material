# Packet 11：权威文档、全量验证和真实只读 smoke

**目标：** 更新权威文档，执行第三期最终门禁，并将 STATE 标记为 complete。

**详细步骤来源：** 完整计划 Task 11 与“第三期完成门禁”。

**完成验证：**

```bash
python -m pytest tests/worldbuilding tests/pipeline tests/audit tests/reporting tests/storage tests/search tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v
python -m novel_material.cli.main pipeline worldbuilding --help
python -m novel_material.cli.main pipeline profile --help
python -m novel_material.cli.main pipeline full --help
python -m novel_material.cli.main pipeline continue --help
python -m novel_material.cli.main search world --help
python -m compileall -q src/novel_material
python scripts/check_v3_docs.py
git diff --check -- . ':(exclude)docs/feedback.md'
git status --short
```

**真实只读 smoke：**

```bash
python -m novel_material.cli.main validate artifacts nm_novel_20260621_4si2
```

允许退出码 `0` 或 `3`，但不得修改非 `reports/` 事实文件。不得在本 packet 中擅自运行真实 `worldbuilding/profile` LLM。

**完成后：** 更新 `STATE.md`，并将 `last_good_commit` 设为最后一次通过门禁的文档提交短 hash：

```yaml
status: complete
current_packet: null
last_completed_packet: task-11-docs-final-verification.md
```

**提交：** `docs(worldbuilding): 完成分层世界观与作品画像文档`
