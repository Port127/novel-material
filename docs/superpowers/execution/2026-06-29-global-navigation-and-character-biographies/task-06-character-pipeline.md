# Packet 06：characters 阶段接入小传与简档

**目标：** characters 阶段消费前置导航和自适应选择，生成完整小传、简档和索引统计。

**详细步骤来源：** 完整计划 `Task 6`。

```bash
sed -n '/^## Task 6：接入人物生成、简档与索引元数据/,/^## Task 7：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/pipeline/test_characters_pipeline_biographies.py tests/pipeline/test_character_selection.py tests/pipeline/test_character_biography.py -v
```

**提交：** `feat(characters): 接入主要人物完整小传生成`
