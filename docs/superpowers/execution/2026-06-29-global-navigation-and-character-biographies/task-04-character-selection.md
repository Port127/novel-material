# Packet 04：自适应人物选择器

**目标：** 基于导航、出场、跨度、关键事件和关系中心度选择 5–12 名完整小传目标。

**详细步骤来源：** 完整计划 `Task 4`。

```bash
sed -n '/^## Task 4：实现自适应人物选择器/,/^## Task 5：/p' docs/superpowers/plans/2026-06-29-global-navigation-and-character-biographies.md
```

**完成验证：**

```bash
python -m pytest tests/pipeline/test_character_selection.py tests/pipeline/test_llm_response_contracts.py -v
```

**提交：** `feat(characters): 增加主要人物自适应选择器`
