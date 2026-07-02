# Packet 3：题材维度路由

**目标：** 实现 `resolve_worldbuilding_dimensions`，把 meta、前置导航和章级信号合并为 applicable / not_applicable 维度列表。

**详细步骤来源：** 完整计划 Task 3。

**关键文件：**

- `src/novel_material/worldbuilding/dimensions.py`
- `tests/worldbuilding/test_dimensions.py`

**完成验证：**

```bash
python -m pytest tests/worldbuilding/test_dimensions.py tests/pipeline/test_profile_resolver.py -v
python -m compileall -q src/novel_material/worldbuilding
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-04-normalizer-contract.md`。

**提交：** `feat(worldbuilding): 增加题材维度路由`
