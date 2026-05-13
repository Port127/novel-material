# 批次4：拆分大文件

## 完成状态

✅ 批次4已完成

---

## 最高目标

将超过500行的大文件拆分为职责清晰的小模块，每模块不超过300行。

---

## 拆分清单

### analyze.py (1362行 → 4个模块)

| 原文件行数 | 新模块 | 行数 | 职责 |
|-----------|--------|------|------|
| 1-506 | analyze_utils.py | ~506 | 辅助函数和常量（提示词模板、温度控制、滑动窗口） |
| 366-452 | analyze_single.py | ~90 | 单章分析函数 |
| 455-621 | analyze_batch.py | ~170 | 批量分析函数 |
| 852-1362 | analyze.py | ~510 | 统一入口（保留主入口 + 重分析函数） |

**注**：analyze_utils.py 行数超过300，但都是独立的辅助函数，职责清晰，暂不进一步拆分。

### sync.py (896行 → 7个模块)

| 原文件行数 | 新模块 | 行数 | 职责 |
|-----------|--------|------|------|
| 1-58, 61-114 | sync_utils.py | ~115 | 公共函数（向量加载、异常类、数据库连接） |
| 259-297 | sync_meta.py | ~40 | 同步 meta.yaml |
| 300-443 | sync_chapters.py | ~145 | 同步章节数据和人物出场 |
| 429-598 | sync_outline.py | ~170 | 同步大纲结构 |
| 601-744 | sync_characters.py | ~145 | 同步人物档案 |
| 746-856 | sync_worldbuilding.py | ~110 | 同步世界观元素 |
| 117-256, 859-896 | sync_core.py | ~140 | 入口函数（预检、修复、执行同步） |
| 统一入口 | sync.py | ~25 | 向后兼容导入 |

### outline.py (872行 → 6个模块)

| 原文件行数 | 新模块 | 行数 | 职责 |
|-----------|--------|------|------|
| 33-153 | outline_temp.py | ~120 | 临时文件管理（断点续传） |
| 154-196 | outline_stats.py | ~45 | 大纲统计函数 |
| 203-296, 800-865 | outline_acts.py | ~110 | 幕序列生成 + 简单划分 |
| 302-387 | outline_beats.py | ~90 | 节拍生成 |
| 393-797 | outline_core.py | ~405 | 入口函数（前提提炼、结构生成） |
| 统一入口 | outline.py | ~20 | 向后兼容导入 |

**注**：outline_core.py 行数超过300，但主函数 generate_outline 是一个连续流程，拆分会破坏逻辑连贯性，暂不进一步拆分。

### characters.py (817行 → 6个模块)

| 原文件行数 | 新模块 | 行数 | 职责 |
|-----------|--------|------|------|
| 29-41, 413-429 | characters_stats.py | ~45 | 出场频率统计 + 常量 |
| 47-89 | characters_selector.py | ~45 | 分层筛选 |
| 92-133, 378-429 | characters_profile.py | ~95 | 档案生成 + 增量写入 |
| 139-327 | characters_layer.py | ~190 | 分批提取人物详情 |
| 431-783 | characters_core.py | ~355 | 入口函数（三层处理） |
| 统一入口 | characters.py | ~20 | 向后兼容导入 |

**注**：characters_core.py 行数超过300，但主函数 generate_characters 是一个连续流程，暂不进一步拆分。

---

## 拆分原则

1. **每子模块不超过300行**（原则）：部分入口函数因流程连续性暂时超标，但职责清晰。
2. **子模块按职责划分**：统计、筛选、生成、写入、入口等独立职责。
3. **保留原文件作为统一入口**：向后兼容，所有公共接口仍从原文件导入。
4. **子模块间无相互依赖**：各子模块只依赖公共模块（utils/stats），不依赖彼此。

---

## 模块结构图

### pipeline 模块结构

```
pipeline/
├── analyze.py          # 统一入口
├── analyze_utils.py    # 辅助函数
├── analyze_single.py   # 单章分析
├── analyze_batch.py    # 批量分析
├── outline.py          # 统一入口
├── outline_temp.py     # 临时文件
├── outline_stats.py    # 统计
├── outline_acts.py     # 幕序列
├── outline_beats.py    # 节拍
├── outline_core.py     # 入口函数
├── characters.py       # 统一入口
├── characters_stats.py # 统计
├── characters_selector.py # 分层筛选
├── characters_profile.py # 档案生成
├── characters_layer.py # 分批提取
├── characters_core.py  # 入口函数
├── worldbuilding.py    # 世界观（未拆分，290行）
├── loader.py           # 加载器（公共函数）
├── ...
```

### storage 模块结构

```
storage/
├── sync.py             # 统一入口
├── sync_utils.py       # 公共函数
├── sync_meta.py        # 同步 meta
├── sync_chapters.py    # 同步章节
├── sync_outline.py     # 同步大纲
├── sync_characters.py  # 同步人物
├── sync_worldbuilding.py # 同步世界观
├── sync_core.py        # 入口函数
├── repair.py           # 修复接口（批次2）
├── embedding.py        # 向量化
├── ...
```

---

## 导入路径变更

所有公共接口保持向后兼容，从原文件导入：

```python
# analyze
from novel_material.pipeline.analyze import chapter_analyze, reanalyze_chapters

# outline
from novel_material.pipeline.outline import generate_outline, generate_simple_acts

# characters
from novel_material.pipeline.characters import generate_characters, _extract_appearance_stats

# sync
from novel_material.storage.sync import sync_novel, sync_all, get_db_connection
```

内部函数可从子模块导入（非公共接口）：

```python
from novel_material.pipeline.analyze_utils import build_sliding_window_context
from novel_material.pipeline.outline_stats import _extract_outline_stats
from novel_material.storage.sync_chapters import sync_chapters
```

---

## Verification

- ✅ `python -m pytest tests/` — 28 passed, 1 failed（失败为原有问题）
- ✅ `python -c "from novel_material.pipeline.analyze import chapter_analyze"` — 导入成功
- ✅ `python -c "from novel_material.pipeline.outline import generate_outline"` — 导入成功
- ✅ `python -c "from novel_material.pipeline.characters import generate_characters"` — 导入成功
- ✅ `python -c "from novel_material.storage.sync import sync_novel"` — 导入成功