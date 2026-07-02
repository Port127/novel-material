# Packet 07：定向人物修复 CLI

**目标：** 支持 `nm pipeline characters <id> --repair-character <name>` 可重复传入，只重建指定人物。

**详细步骤来源：** 完整计划 `Task 7`。

```bash
sed -n '/^## Task 7：增加定向人物修复 CLI/,/^## Task 8：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/cli/test_character_repair_contract.py tests/pipeline/test_characters_pipeline_biographies.py -v
python -m novel_material.cli.main pipeline characters --help
```

**提交：** `feat(characters): 支持定向重建人物小传`
