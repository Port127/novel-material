# 批次3：消除代码重复

## 完成状态

✅ 批次3已完成

---

## 最高目标

使用公共模块替换所有重复代码，统一实现逻辑。

---

## 改动清单

### 修改文件

| 文件 | 改动内容 |
|------|----------|
| `pipeline/loader.py` | 新增 `build_analysis_context` 公共函数 |
| `pipeline/__init__.py` | 导出 `build_analysis_context` |
| `pipeline/worldbuilding.py` | 1. 删除 `_build_context` 定义<br>2. 导入并调用 `build_analysis_context`<br>3. 使用 `is_special_chapter_type` |
| `pipeline/characters.py` | 1. 删除 `_build_context` 定义<br>2. 导入并调用 `build_analysis_context`<br>3. 使用 `is_special_chapter_type` |
| `pipeline/outline.py` | 使用 `is_special_chapter_type` 替换硬编码过滤 |
| `storage/sync.py` | 使用 `is_special_chapter_type` 替换硬编码过滤 |

---

## 重复代码消除统计

| 重复项 | 原位置 | 新位置 |
|--------|--------|--------|
| `_build_context` | worldbuilding.py:84-113, characters.py:431-459 | pipeline/loader.py:build_analysis_context |
| 特殊类型过滤 | outline.py、worldbuilding.py、characters.py、sync.py 共 6 处 | infra/common.py:is_special_chapter_type |

---

## 公共函数使用示例

### build_analysis_context

```python
from novel_material.pipeline.loader import build_analysis_context

# 构建世界观分析上下文
context_text, context_label = build_analysis_context(
    novel_dir, config, chapters_data,
    material_id=material_id,
    summary_tokens_key="worldbuilding_summary_tokens",
    fallback_chars=10000,
)

# 构建人物分析上下文
context_text, context_label = build_analysis_context(
    novel_dir, config, chapters_data,
    material_id=material_id,
    summary_tokens_key="characters_summary_tokens",
    fallback_chars=8000,
)
```

### is_special_chapter_type

```python
from novel_material.infra.common import is_special_chapter_type

# 跳过特殊章节
for ch in chapters_data:
    if is_special_chapter_type(ch.get("type", "normal")):
        continue
    # 处理正文...
```

---

## 迁移注意事项

1. **`build_analysis_context` 参数说明**：
   - `summary_tokens_key`: config["llm"] 中摘要池 token 配置的键名
   - `fallback_chars`: 原文兜底时的字符数
   - 不同模块使用不同的默认值（worldbuilding=10000, characters=8000）

2. **特殊章节过滤统一**：
   - 所有使用 `"afterword", "author_note"` 硬编码的地方都已改为调用 `is_special_chapter_type`
   - 函数封装在 infra/common.py，便于后续修改特殊类型定义

---

## Verification

- ✅ `python -c "from novel_material.pipeline.loader import build_analysis_context"` — 导入成功
- ✅ `python -m pytest tests/` — 28 passed, 1 failed（失败为原有问题）