# 项目架构重构执行批次计划

## Context

项目 `/Users/kiki/Documents/Project/my-github/novel/novel-material/src/novel_material` 从几个文件膨胀到 57 个文件、~13,600 行代码。存在严重的分层依赖问题、代码重复、大文件未拆分、测试覆盖不足等问题。

**所有问题都是最高优先级**，关键是执行顺序：先修复架构基础，再拆分大文件，最后补充测试。

---

## 批次总览

```
批次1 → 批次2 → 批次3 → 批次4 → 批次5 → 批次6
(公共基础) (解除依赖) (消除重复) (文件拆分) (接口收敛) (测试覆盖)
```

---

## 批次1：建立公共基础模块

### 最高目标
扩展 infra 层为公共函数基础，为后续重构提供可复用的工具。

### 具体步骤

| 文件 | 改动内容 |
|------|----------|
| `infra/common.py`（新建） | 1. 合入 `constants.py` 的现有常量<br>2. 新增 `is_special_chapter_type(ch_type: str) -> bool`<br>3. 新增 `filter_normal_chapters(chapters_data: list) -> list`<br>4. 新增 `generate_material_id() -> str`（从 ingest.py 提取） |
| `infra/constants.py` | 内容迁移到 common.py，保留为空壳或删除 |
| `pipeline/ingest.py:26-39` | 移除 `generate_material_id`，改为从 `infra.common` 导入 |
| `material/import_material.py:15-19` | 移除 `generate_material_id`，改为从 `infra.common` 导入 |
| 所有使用常量的文件 | 更新导入路径为 `infra.common` |

### 预期产出文档
`docs/refactor/01-common-module.md`
- 公共函数列表与接口规范
- 使用示例代码
- 迁移注意事项

### 依赖关系
无前置依赖（首批执行）

---

## 批次2：解除反向依赖

### 最高目标
建立正确的分层架构，消除 storage/validation/material 对 pipeline/tags 的反向/跨层依赖。

### 具体步骤

| 文件 | 改动内容 |
|------|----------|
| `storage/repair.py`（新建） | 从 `pipeline/analyze.py` 提取 `repair_short_summaries` 及依赖的辅助函数（约200-300行） |
| `pipeline/analyze.py:1288-1356` | 移除 `repair_short_summaries`，保留对外调用接口（调用 storage.repair） |
| `storage/sync.py:23` | 修改导入：`from novel_material.storage.repair import repair_short_summaries` |
| `infra/tag_utils.py`（新建） | 从 `tags/validate.py` 提取 `validate_tag`、`validate_tags_batch`（纯校验逻辑） |
| `validation/tag_rules.py:1-2` | 修改导入：`from novel_material.infra.tag_utils import ...` |
| `validation/schema.py:33` | 修改导入：`from novel_material.infra.tag_utils import ...` |
| `material/import_material.py:12` | 修改导入：`from novel_material.infra.tag_utils import ...` |

### 分层架构（修正后）
```
infra（公共层）
  ↑
validation / material（从 infra 导入公共工具）
  ↑
pipeline（流水线层）
  ↑
storage（存储层，同层调用 storage.repair）
```

### 预期产出文档
`docs/refactor/02-dependency-fix.md`
- 分层架构图（更新版）
- 依赖关系变更清单
- 模块职责边界说明

### 依赖关系
依赖批次1

---

## 批次3：消除代码重复

### 最高目标
使用公共模块替换所有重复代码，统一实现逻辑。

### 具体步骤

| 文件 | 改动内容 |
|------|----------|
| `infra/common.py`（扩展） | 新增 `_build_analysis_context(novel_dir, config, chapters_data, material_id) -> tuple[str, str]` |
| `pipeline/worldbuilding.py:84-113` | 删除 `_build_context`，调用 `infra.common._build_analysis_context` |
| `pipeline/characters.py:431-459` | 删除 `_build_context`，调用 `infra.common._build_analysis_context` |
| `pipeline/outline.py:172-174` | 特殊章节过滤改为 `is_special_chapter_type(ch_type)` |
| `pipeline/characters.py:424-428` | 特殊章节过滤改为 `is_special_chapter_type(ch_type)` |
| `pipeline/worldbuilding.py:54-56` | 特殊章节过滤改为 `is_special_chapter_type(ch_type)` |
| `storage/sync.py:732-733` | 特殊章节过滤改为 `is_special_chapter_type(ch_type)` |

### 重复代码消除统计
| 重复项 | 原位置 | 新位置 |
|--------|--------|--------|
| `generate_material_id` | ingest.py, import_material.py | infra/common.py |
| `_build_context` | worldbuilding.py, characters.py | infra/common.py |
| 特殊类型过滤 | 6个文件多处 | infra/common.py |

### 预期产出文档
`docs/refactor/03-code-duplication.md`
- 重复代码消除清单
- 公共函数使用指南
- 迁移前后对比代码片段

### 依赖关系
依赖批次1、批次2

---

## 批次4：拆分大文件

### 最高目标
将超过500行的大文件拆分为职责清晰的小模块，每模块不超过300行。

### 具体步骤

| 原文件 | 拆分方案 |
|--------|----------|
| `pipeline/analyze.py` (1362行) | 拆为：<br>`analyze_core.py`（入口，~300行）<br>`analyze_single.py`（单章分析）<br>`analyze_batch.py`（批量分析）<br>`analyze_utils.py`（辅助函数）<br>保留原文件作为统一入口 |
| `storage/sync.py` (895行) | 拆为：<br>`sync_core.py`（入口）<br>`sync_meta.py`<br>`sync_chapters.py`<br>`sync_outline.py`<br>`sync_characters.py`<br>`sync_worldbuilding.py`<br>保留原文件作为统一入口 |
| `pipeline/outline.py` (872行) | 拆为：<br>`outline_core.py`（入口）<br>`outline_acts.py`<br>`outline_beats.py`<br>`outline_stats.py`<br>`outline_temp.py`<br>保留原文件作为统一入口 |
| `pipeline/characters.py` (817行) | 拆为：<br>`characters_core.py`（入口）<br>`characters_selector.py`<br>`characters_profile.py`<br>`characters_stats.py`<br>`characters_layer.py`<br>保留原文件作为统一入口 |

### 拆分原则
1. 每个子模块不超过300行
2. 子模块按职责划分
3. 保留原文件作为统一入口，向后兼容
4. 子模块间无相互依赖

### 预期产出文档
`docs/refactor/04-file-split.md`
- 拆分后的模块结构图
- 各子模块职责说明
- 导入路径变更清单

### 依赖关系
依赖批次1、批次2、批次3

---

## 批次5：收敛接口暴露

### 最高目标
精简 `pipeline/__init__.py` 导出列表，只暴露必要的公共接口。

### 具体步骤

| 文件 | 改动内容 |
|------|----------|
| `pipeline/__init__.py` | 当前导出27项，精简为约12项：<br>**保留**：`ingest_file`、`chapter_analyze`、`generate_outline`、`generate_worldbuilding`、`generate_characters`、`generate_tags`、`refine`、`run_evaluation`、`get_pipeline_progress`、`print_pipeline_status`、`get_next_pending_stage`<br>**移除**：`preprocess`、`load_chapters_data`、`build_summary_pool`、`infer_key_plot_points`、`generate_simple_acts`、`refine_outline`、`refine_characters`、`refine_tags` 等内部函数 |
| `cli/pipeline.py` | 更新导入路径，内部函数从具体子模块导入 |

### 预期产出文档
`docs/refactor/05-interface-refine.md`
- 公共接口列表
- 内部接口列表
- 导入路径变更指南

### 依赖关系
依赖批次4

---

## 批次6：增加测试覆盖

### 最高目标
为核心模块增加测试，目标覆盖率80%。

### 具体步骤

| 测试文件 | 新增内容 |
|----------|----------|
| `tests/infra/test_common.py`（新建） | 测试公共函数 |
| `tests/storage/test_repair.py`（新建） | 测试 repair 模块 |
| `tests/storage/test_sync.py`（新建） | 测试同步逻辑 |
| `tests/pipeline/test_analyze.py`（新建） | 测试核心分析流程 |
| `tests/pipeline/test_outline.py`（新建） | 测试大纲生成 |
| `tests/pipeline/test_characters.py`（新建） | 测试人物提取 |
| `tests/conftest.py`（扩展） | 添加 mock fixture |

### 预期产出文档
`docs/refactor/06-test-coverage.md`
- 测试文件列表与覆盖率目标
- Mock策略说明
- 测试运行指南

### 依赖关系
依赖批次1-5全部完成

---

## 关键文件清单

实现此重构计划最关键的文件：

- `infra/constants.py` — 扩展为公共模块的核心位置
- `storage/sync.py` — 反向依赖问题核心，需拆分
- `pipeline/analyze.py` — 最大文件(1362行)，含需移出的 repair 函数
- `validation/tag_rules.py` — 反向依赖问题验证层代表
- `pipeline/__init__.py` — 接口收敛核心文件

---

## Verification

每批次完成后需执行：
1. `python -m pytest tests/` — 运行现有测试确保无回归
2. `python -c "from novel_material.pipeline import chapter_analyze"` — 验证导入正常
3. 检查 `docs/refactor/` 目录下对应文档已生成