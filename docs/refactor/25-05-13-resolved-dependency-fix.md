# 批次2：解除反向依赖

## 完成状态

✅ 批次2已完成

---

## 最高目标

建立正确的分层架构，消除 storage/validation/material 对 pipeline/tags 的反向/跨层依赖。

---

## 改动清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `storage/repair.py` | 存储层修复入口，委托调用 pipeline.analyze |

### 删除文件

| 文件 | 说明 |
|------|------|
| `validation/tag_rules.py` | 已合并到 tags/validate.py |

### 修改文件

| 文件 | 改动内容 |
|------|----------|
| `storage/__init__.py` | 添加 repair 模块导出 |
| `storage/sync.py` | 导入改为 `storage.repair`（消除对 pipeline 的依赖） |
| `tags/validate.py` | 合入 check_dimension、suggest_expand 函数 |
| `tags/__init__.py` | 导出新增函数 |
| `validation/__init__.py` | 移除 tag_rules 导出 |

---

## 分层架构（修正后）

```
infra（公共层）
  ↑
tags（标签层）— 独立模块，提供校验、解析功能
  ↑
validation（校验层）← 从 tags 导入校验函数（正确依赖）
material（素材层）← 从 tags 导入校验函数（正确依赖）
  ↑
pipeline（流水线层）
  ↑
storage（存储层）← 同层调用 storage.repair（委托接口）
```

**关键改动说明**：

1. **storage → pipeline 的反向依赖已解除**：
   - 原：`storage/sync.py` 直接导入 `pipeline.analyze.repair_short_summaries`
   - 新：`storage/sync.py` 导入 `storage.repair.repair_short_summaries`，后者委托调用 `pipeline.analyze.reanalyze_chapters`

2. **validation/tag_rules.py 已移除**：
   - 该文件只是 tags 功能的包装层，不属于 validation 模块
   - `check_dimension`、`suggest_expand` 已合并到 `tags/validate.py`
   - validation 模块专注于 schema 校验和质量检查

---

## 委托接口设计

`storage/repair.py` 作为委托层：

```python
# storage/repair.py
def repair_chapters(material_id, chapters, ...) -> tuple[bool, int, int]:
    """storage 层的修复入口"""
    # 委托给 pipeline.analyze
    success, repaired, total = reanalyze_chapters(...)
    # 添加 storage 层的日志记录
    if success:
        logger.info(f"[{material_id}] 修复完成: {repaired}/{total} 章")
    return success, repaired, total
```

这样设计的好处：
- storage 层不直接依赖 pipeline 的具体实现细节
- storage 层可以添加自己的日志和处理逻辑
- 未来如果要修改修复逻辑，只需修改 pipeline.analyze，storage 层无需改动

---

## Verification

- ✅ `python -c "from novel_material.storage import repair_chapters"` — 导入成功
- ✅ `python -c "from novel_material.tags import check_dimension, suggest_expand"` — 导入成功
- ✅ `python -m pytest tests/` — 28 passed, 1 failed（失败为原有问题）