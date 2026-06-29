# Packet 10：性能预算与真实只读 smoke

**目标：** 增加 1084 章/134 人物候选的本地预算测试，并执行真实素材只读 smoke。

**详细步骤来源：** 完整计划 `Task 10`。

```bash
sed -n '/^## Task 10：性能预算与真实 smoke 验收/,/^## Task 11：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**禁止：** 默认不执行真实 LLM 修复；真实 `pipeline characters --repair-character` 必须另行问用户。

**完成验证：**

```bash
python -m pytest tests/pipeline/test_character_performance_budget.py tests/reporting/test_performance_baseline.py -v
python -m pytest tests/audit tests/reporting tests/runtime tests/run_logging tests/pipeline tests/terminal tests/cli/test_pipeline_contract.py tests/cli/test_command_contracts.py tests/validation -v
python -m novel_material.cli.main validate artifacts nm_novel_20260621_4si2
```

真实素材命令预期退出码 3；需记录非 `reports/` 文件哈希不变。

**提交：** `test(characters): 增加小传选择性能预算`
