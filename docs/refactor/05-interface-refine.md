# 批次5：收敛接口暴露

## 完成状态

✅ 批次5已完成

---

## 最高目标

精简 pipeline/__init__.py 导出列表，只暴露必要的公共接口。

---

## 导出变更

### 原导出列表（26项）

```python
__all__ = [
    "preprocess",
    "preprocess_text",
    "load_chapters_data",
    "build_summary_pool",
    "build_analysis_context",
    "ingest_file",
    "chapter_analyze",
    "infer_key_plot_points",
    "KEY_PLOT_POINT_VALUES",
    "refine",
    "refine_outline",
    "refine_characters",
    "refine_tags",
    "generate_outline",
    "generate_simple_acts",
    "generate_worldbuilding",
    "generate_characters",
    "generate_tags",
    "get_pipeline_progress",
    "print_pipeline_status",
    "get_next_pending_stage",
    "PIPELINE_STAGES",
    "get_pipeline_stages",
    "calculate_total_stages",
    "calculate_current_stage",
    "run_evaluation",
]
```

### 新导出列表（11项）

```python
__all__ = [
    # 公共接口
    "ingest_file",
    "chapter_analyze",
    "generate_outline",
    "generate_worldbuilding",
    "generate_characters",
    "generate_tags",
    "refine",
    "run_evaluation",
    "get_pipeline_progress",
    "print_pipeline_status",
    "get_next_pending_stage",
]
```

---

## 移除的接口

| 接口 | 原位置 | 新位置 | 说明 |
|------|--------|--------|------|
| `preprocess` | pipeline/__init__.py | pipeline.preprocess | 内部预处理函数 |
| `preprocess_text` | pipeline/__init__.py | pipeline.preprocess | 内部预处理函数 |
| `load_chapters_data` | pipeline/__init__.py | pipeline.loader | 内部加载函数 |
| `build_summary_pool` | pipeline/__init__.py | pipeline.loader | 内部摘要池函数 |
| `build_analysis_context` | pipeline/__init__.py | pipeline.loader | 内部上下文函数 |
| `infer_key_plot_points` | pipeline/__init__.py | pipeline.infer | 内部推断函数 |
| `KEY_PLOT_POINT_VALUES` | pipeline/__init__.py | infra.common | 内部常量 |
| `refine_outline` | pipeline/__init__.py | pipeline.refine | 内部精修函数 |
| `refine_characters` | pipeline/__init__.py | pipeline.refine | 内部精修函数 |
| `refine_tags` | pipeline/__init__.py | pipeline.refine | 内部精修函数 |
| `generate_simple_acts` | pipeline/__init__.py | pipeline.outline_acts | 内部兜底函数 |
| `PIPELINE_STAGES` | pipeline/__init__.py | pipeline.progress | 内部常量 |
| `get_pipeline_stages` | pipeline/__init__.py | pipeline.progress | 内部函数 |
| `calculate_total_stages` | pipeline/__init__.py | pipeline.progress | 内部函数 |
| `calculate_current_stage` | pipeline/__init__.py | pipeline.progress | 内部函数 |

---

## 导入路径变更指南

### 公共接口（推荐）

```python
# 从 pipeline/__init__.py 导入（推荐）
from novel_material.pipeline import (
    ingest_file,
    chapter_analyze,
    generate_outline,
    generate_worldbuilding,
    generate_characters,
    generate_tags,
    refine,
    run_evaluation,
    get_pipeline_progress,
    print_pipeline_status,
    get_next_pending_stage,
)
```

### 内部接口（从具体子模块导入）

```python
# 预处理
from novel_material.pipeline.preprocess import preprocess, preprocess_text

# 加载器
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool, build_analysis_context

# 推断
from novel_material.pipeline.infer import infer_key_plot_points

# 常量
from novel_material.infra.common import KEY_PLOT_POINT_VALUES

# 精修
from novel_material.pipeline.refine import refine_outline, refine_characters, refine_tags

# 大纲兜底
from novel_material.pipeline.outline_acts import generate_simple_acts

# 进度
from novel_material.pipeline.progress import (
    PIPELINE_STAGES,
    get_pipeline_stages,
    calculate_total_stages,
    calculate_current_stage,
)
```

---

## cli/pipeline.py 更新

cli/pipeline.py 已正确从子模块导入内部接口：

```python
from novel_material.pipeline import (
    ingest_file,
    chapter_analyze,
    generate_outline,
    generate_worldbuilding,
    generate_characters,
    generate_tags,
    refine,
    run_evaluation,
)
from novel_material.pipeline.progress import (
    get_pipeline_progress,
    print_pipeline_status,
    get_next_pending_stage,
    calculate_total_stages,
    calculate_current_stage,
    get_pipeline_stages,
)
```

---

## Verification

- ✅ `python -c "from novel_material.pipeline import chapter_analyze"` — 公共接口导入成功
- ✅ `python -c "from novel_material.pipeline.loader import load_chapters_data"` — 内部接口导入成功
- ✅ `python -m pytest tests/` — 28 passed, 1 failed（失败为原有问题）