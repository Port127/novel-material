# Packet 2：世界观契约模型与旧格式兼容读取

**目标：** 新增 `novel_material.worldbuilding` 契约模型和统一读取器，支持 layered 与 legacy 世界观只读加载。

**详细步骤来源：** 完整计划 Task 2。

**关键文件：**

- `src/novel_material/worldbuilding/models.py`
- `src/novel_material/worldbuilding/reader.py`
- `tests/worldbuilding/test_reader.py`
- `tests/worldbuilding/test_models.py`

**完成验证：**

```bash
python -m pytest tests/worldbuilding/test_reader.py tests/worldbuilding/test_models.py -v
python -m compileall -q src/novel_material/worldbuilding
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-03-dimension-router.md`。

**提交：** `feat(worldbuilding): 增加分层世界观读取契约`
