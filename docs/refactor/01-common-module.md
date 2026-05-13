# 批次1：建立公共基础模块

## 完成状态

✅ 批次1已完成

---

## 最高目标

扩展 infra 层为公共函数基础，为后续重构提供可复用的工具。

---

## 改动清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `infra/common.py` | 公共函数与常量模块 |

### 修改文件

| 文件 | 改动内容 |
|------|----------|
| `infra/__init__.py` | 添加从 common.py 的导入和导出 |
| `pipeline/ingest.py` | 移除 `generate_material_id`，改从 infra.common 导入 |
| `pipeline/__init__.py` | 移除 `generate_material_id` 导出，常量改从 infra.common 导入 |
| `pipeline/infer.py` | 常量导入路径改为 infra.common |
| `pipeline/evaluate.py` | 常量导入路径改为 infra.common |
| `pipeline/analyze.py` | 常量导入路径改为 infra.common |
| `validation/schema.py` | 常量导入路径改为 infra.common |
| `material/__init__.py` | 移除 `generate_material_id` 导出 |
| `material/import_material.py` | 移除 `generate_material_id`，改从 infra.common 导入 |

---

## 公共函数列表

### 常量

```python
KEY_PLOT_POINT_VALUES = [...]  # 章节结构角色标记
NOVEL_TYPE_VALUES = [...]       # 小说类型
TENSION_CHANGE_VALUES = [...]   # 张力变化方向
HOOK_TYPE_VALUES = [...]        # 章末钩子类型
SPECIAL_CHAPTER_TYPES = ("afterword", "author_note")  # 特殊章节类型
VALID_CHAPTER_TYPES = ("normal", "extra")             # 有效正文类型
```

### 函数

```python
def is_special_chapter_type(ch_type: str) -> bool:
    """判断章节是否为特殊类型（不参与正文分析）"""
    return ch_type in SPECIAL_CHAPTER_TYPES

def is_valid_chapter_type(ch_type: str) -> bool:
    """判断章节是否为有效正文类型"""
    return ch_type in VALID_CHAPTER_TYPES

def filter_normal_chapters(chapters_data: list) -> list:
    """过滤出正文章节，排除特殊类型"""
    return [ch for ch in chapters_data if is_valid_chapter_type(ch.get("type", "normal"))]

def generate_material_id(novels_dir: Path | None = None) -> str:
    """生成唯一的素材 ID，格式：nm_novel_YYYYMMDD_xxxx"""
```

---

## 使用示例

```python
# 从 infra 导入公共函数和常量
from novel_material.infra import (
    is_special_chapter_type,
    filter_normal_chapters,
    generate_material_id,
    KEY_PLOT_POINT_VALUES,
)

# 判断章节类型
if is_special_chapter_type(ch.get("type", "normal")):
    continue  # 跳过后记、作者说等

# 过滤正文章节
normal_chapters = filter_normal_chapters(chapters_data)

# 生成素材 ID
material_id = generate_material_id(novels_dir=NOVELS_DIR)
```

---

## 迁移注意事项

1. **导入路径变更**：
   - 原：`from novel_material.infra.constants import KEY_PLOT_POINT_VALUES`
   - 新：`from novel_material.infra.common import KEY_PLOT_POINT_VALUES` 或 `from novel_material.infra import KEY_PLOT_POINT_VALUES`

2. **generate_material_id 变更**：
   - 原：从 `pipeline` 或 `material` 导入
   - 新：从 `infra` 导入
   - 新增可选参数 `novels_dir` 用于冲突检测

3. **向后兼容**：
   - `infra/__init__.py` 已导出所有公共函数，可直接 `from novel_material.infra import ...`
   - `constants.py` 保留但不推荐直接导入

---

## Verification

- ✅ `python -c "from novel_material.infra import is_special_chapter_type, generate_material_id"` — 导入成功
- ✅ `python -c "from novel_material.pipeline import ingest_file, chapter_analyze"` — 导入成功
- ✅ `python -m pytest tests/` — 28 passed, 1 failed（失败为原有问题，非回归）