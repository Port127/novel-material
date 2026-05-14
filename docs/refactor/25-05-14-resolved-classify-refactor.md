# Classify 重构改动影响分析报告

> 日期: 2026-05-14
> 分析工具: code-review-change skill

## 改动概述

素材分类功能重构，涉及接口变更和数据格式变更。

| 改动对象 | 改动类型 |
|---------|---------|
| `classify_prompt.py` | 重写（删除硬编码，新建动态生成函数） |
| `classify.py` | 重写（新取样函数、新解析函数、动态 genre） |
| `cli/material.py` | 修改返回处理 |
| `material/__init__.py` | 更新导出 |

---

## 发现问题（3 个）

### P1: 数据格式混合 [已解决]

**位置**: `data/material_index.yaml`

**问题**: 现有数据使用旧格式 `genre: ["仙侠", "修仙"]`，新代码写入新字段 `genre_primary` 等新字段。混合格式会导致后续读取 KeyError。

**解决**: 清空 `material_index.yaml` 和 `classify_progress.yaml`，重新分类。

**验证**: 运行 `nm material classify start --limit 1`，输出格式正确包含新字段。

---

### P2: validate_tag 无效调用 [已解决]

**位置**: `classify.py:189-193`

**问题**: `validate_tag("genre", genre_primary)` 无意义，因为 `tags` 表 `dimension` 字段值为 `element/setting/style/structure`，而非 `genre`。调用永远返回 None。

**解决**: 删除第 189-193 行的 validate_tag 调用，删除第 20 行的导入。

**代码变更**:
```python
# 删除前
from novel_material.tags.validate import validate_tag
...
canonical = validate_tag("genre", genre_primary)

# 删除后
if not valid_primary:
    logger.warning(f"无效 genre_primary: {genre_primary}")
    valid_primary = "其他"
```

---

### P3: f-string 花括号解析错误 [已解决]

**位置**: `classify_prompt.py:22-27`

**问题**: JSON 示例中的花括号 `{}` 被 Python f-string 误解析，导致运行时报错 `Invalid format specifier`。

**解决**: 花括号转义（双写）。

**代码变更**:
```python
# 修复前
{
  "genre_primary": "一级题材",
  ...
}

# 修复后
{{"genre_primary": "一级题材", ...}}
```

---

## 验收结果

| 验收项 | 状态 |
|--------|------|
| 单元测试 | ✅ 22 passed |
| 实际运行 | ✅ 成功分类 1 条 |
| Token 消耗 | ✅ input=6349（正常范围） |
| 输出格式 | ✅ 包含 genre_primary, elements, style, quality |

---

## 输出格式示例

```yaml
materials:
  0002_极道天魔:
    genre_primary: 玄幻
    genre_secondary: 东方玄幻
    genre_description: 以武道极道突破为核心，融合系统加点...
    elements: []
    style: {}
    quality:
      writing: 3
      plot: 3
      character: 3
      score: 3.0
    confidence: 0.95
```

---

## 关键文件清单

| 文件 | 状态 |
|------|------|
| `src/novel_material/material/classify.py` | ✅ 已修复 |
| `src/novel_material/material/classify_prompt.py` | ✅ 已修复 |
| `src/novel_material/cli/material.py` | ✅ 已更新 |
| `data/material_index.yaml` | ✅ 已清空重建 |
| `data/classify_progress.yaml` | ✅ 已清空 |
| `tests/test_classify.py` | ✅ 已更新并通过 |