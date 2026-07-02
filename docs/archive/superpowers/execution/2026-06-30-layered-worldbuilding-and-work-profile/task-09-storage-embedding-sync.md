# Packet 9：embedding 与 storage 兼容新世界观

**目标：** 让世界观向量化和数据库同步通过统一读取器支持 layered 与 legacy 世界观。

**详细步骤来源：** 完整计划 Task 9。

**关键文件：**

- `src/novel_material/storage/embedding.py`
- `src/novel_material/storage/sync_worldbuilding.py`
- `tests/storage/test_search_tokens_sync.py`
- `tests/storage/test_worldbuilding_embedding.py`

**完成验证：**

```bash
python -m pytest tests/storage/test_search_tokens_sync.py tests/storage/test_worldbuilding_embedding.py -v
python -m compileall -q src/novel_material/storage src/novel_material/worldbuilding
git diff --check -- . ':(exclude)docs/feedback.md'
```

**完成后：** 更新 `STATE.md` 指向 `task-10-search-world-metadata.md`。

**提交：** `feat(storage): 兼容分层世界观同步与向量化`
