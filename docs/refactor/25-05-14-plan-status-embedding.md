# 重构计划：状态管理与向量化统一

> 本文档解决状态流转不完整、向量化记录缺失、进度检测不准确三个核心问题。

---

## 执行原则

- **敢于删除**：不留兼容层、过渡函数、历史遗留
- **先建后删**：先建 → 改引用 → 验证 → 删除
- **改完验证**：失败就修，不回退

---

## 第一部分：问题分析

### 1.1 状态定义与设计不一致

| 来源 | 定义 |
|------|------|
| **AGENTS.md（设计）** | `clean → evaluated → analyzed → finalized` |
| **config.py（实现）** | `{"raw", "clean", "analyzed", "indexed", "failed"}` |

**问题数据**：
- `indexed` 从未使用（历史遗留）
- `evaluated` 设计中存在，代码无定义
- `finalized` 设计中存在，代码无定义

**后果**：校验会拒绝合法状态，手动设置 `finalized` 会报错。

### 1.2 状态更新职责缺失

| 模块 | 应设置 | 实际行为 |
|------|--------|----------|
| `ingest.py` | `clean` | ✅ 正确 |
| `analyze.py` | `analyzed` | ✅ 正确（调用 `update_meta_status`） |
| `evaluate.py` | `evaluated` | ❌ **未更新** |
| `refine.py` | `finalized` | ❌ **只设置 `refined_at`** |

**grep 定位**：
```bash
# 只有 analyze.py 调用 update_meta_status
grep -rn "update_meta_status" src/novel_material/pipeline/*.py
# 输出: analyze.py:30, 558, 586, 589
```

**后果**：status 永远停留在 `analyzed`，无法区分"章级分析完成"和"全流程完成"。

### 1.3 向量化历史记录缺失

**问题**：向量调用在 `save_history()` 之后，不记录到 run_history。

| 模块 | save_history 位置 | embed 调用位置 |
|------|-------------------|----------------|
| characters_core.py | 366行 | 372行（**之后**） |
| worldbuilding.py | 261行 | 271行（**之后**） |
| refine.py | 无历史 | 203行（embed_outline） |

**grep 定位**：
```bash
grep -n "save_history\|embed_" src/novel_material/pipeline/characters_core.py
# 输出:
# 366: runner.save_history(status="success")
# 372: embed_characters(material_id)
```

**后果**：
- `CHARACTERS_STAGES = 4` 定义包含向量化，但 run_history 只记录 3 个
- 向量化失败时无历史追踪
- 用户无法从 run_history 知道向量化是否完成

### 1.4 进度检测不检查向量文件

**问题**：progress.py 只检查骨架文件，不检查向量文件。

```python
# progress.py:109
"characters": (novel_dir / "characters" / "_index.yaml").exists(),
# 缺少向量检查
```

**后果**：
- 人物向量中断后，continue 认为阶段已完成并跳过
- 数据不完整但状态显示"完成"

### 1.5 历史记录方式分散

| 模块 | 使用方式 |
|------|----------|
| analyze.py | PipelineRunner |
| outline_logic.py | PipelineRunner |
| characters_core.py | PipelineRunner |
| worldbuilding.py | save_run_history() |
| tags.py | save_run_history() |
| evaluate.py | save_run_history() |
| **refine.py** | ❌ 无历史记录 |

**问题**：7 个模块用 2 种方式，refine.py 完全无记录。

---

## 第二部分：解决方案

### 批次规划

```
批次1（基础设施）: 状态定义统一
    ↓
批次2（核心修复）: 状态更新补全
    ↓
批次3（向量化统一）: 创建统一入口 + 改引用
    ↓
批次4（进度完善）: 添加向量检查
    ↓
批次5（清理）: 删除冗余代码
```

---

## 批次1：状态定义统一

### 目标

统一状态定义，删除历史遗留 `indexed`，添加 `evaluated`、`finalized`。

### 步骤1：修改 config.py

**定位**：
```bash
grep -n "VALID_STATUSES" src/novel_material/infra/config.py
```

**改动**：
```python
# 改前
VALID_STATUSES = {"raw", "clean", "analyzed", "indexed", "failed"}

# 改后
VALID_STATUSES = {"raw", "clean", "evaluated", "analyzed", "finalized", "failed"}
```

### 步骤2：更新 AGENTS.md 状态流转说明

**定位**：
```bash
grep -n "状态流转" AGENTS.md
```

**改动**：确保与代码一致（已正确，无需改）。

### 步骤3：验证

```bash
python -c "from novel_material.infra.config import VALID_STATUSES; print(VALID_STATUSES)"
# 期望输出: {'analyzed', 'clean', 'evaluated', 'failed', 'finalized', 'raw'}
```

---

## 批次2：状态更新补全

### 目标

补全 evaluate.py 和 refine.py 的状态更新。

### 步骤1：修改 evaluate.py

**定位**：
```bash
grep -n "save_run_history" src/novel_material/pipeline/evaluate.py
```

**改动**：在 `save_run_history()` 之前添加状态更新。
```python
# 改前
save_run_history(...)

# 改后
from novel_material.infra.config import update_meta_status
update_meta_status(material_id, "evaluated")
save_run_history(...)
```

### 步骤2：修改 refine.py

**定位**：
```bash
grep -n "meta\[\"refined_at\"\]" src/novel_material/pipeline/refine.py
```

**改动**：
```python
# 改前
meta["refined_at"] = time.strftime(...)
save_yaml(meta_file, meta)

# 改后
from novel_material.infra.config import update_meta_status
meta["refined_at"] = time.strftime(...)
save_yaml(meta_file, meta)
update_meta_status(material_id, "finalized")
```

### 步骤3：验证

```bash
# 模拟运行（使用已有素材）
nm pipeline status nm_novel_20260514_l362
# 检查 meta.yaml status 字段是否可设置为 finalized
```

---

## 批次3：向量化统一入口

### 目标

创建统一的向量化入口函数，所有向量调用集中管理并记录历史。

### 步骤1：新建 embed_all.py

**位置**：`src/novel_material/pipeline/embed_all.py`

**关键函数签名**：
```python
def embed_all(material_id: str) -> dict:
    """统一向量化入口，返回完成状态。
    
    处理顺序: chapters → characters → worldbuilding → outline
    
    Returns:
        {"chapters": bool, "characters": bool, "worldbuilding": bool, "outline": bool}
    """
```

**核心逻辑**：
```python
from novel_material.storage.embedding import (
    embed_chapters, embed_characters, embed_worldbuilding, embed_outline
)
from novel_material.infra.progress import save_run_history

def embed_all(material_id: str) -> dict:
    results = {}
    # 逐个调用，记录每个结果
    try:
        embed_chapters(material_id)
        results["chapters"] = True
    except Exception:
        results["chapters"] = False
    
    # 同理处理 characters, worldbuilding, outline
    
    # 保存历史
    save_run_history(novel_dir, pipeline_name="向量化", stage_times=..., status="success" if all(results.values()) else "partial")
    return results
```

### 步骤2：改引用 - CLI pipeline.py

**定位**：
```bash
grep -n "embed_chapters\|embed_characters\|embed_worldbuilding\|embed_outline" src/novel_material/cli/pipeline.py
```

**改动**：在 `full` 和 `continue` 命令中替换分散调用为统一入口。
```python
# 改前（分散在各阶段后）
# 无显式调用，依赖各模块内部调用

# 改后
# 在 refine 阶段后统一调用 embed_all(material_id)
```

### 步骤3：改引用 - characters_core.py

**定位**：
```bash
grep -n "embed_characters" src/novel_material/pipeline/characters_core.py
```

**改动**：
```python
# 改前
runner.save_history(status="success")
embed_characters(material_id)

# 改后（删除 embed 调用，由统一入口处理）
runner.save_history(status="success")
# embed_characters(material_id)  # 移到 embed_all 统一调用
```

### 步骤4：改引用 - worldbuilding.py

**定位**：
```bash
grep -n "embed_worldbuilding" src/novel_material/pipeline/worldbuilding.py
```

**改动**：
```python
# 改前
save_run_history(...)
embed_worldbuilding(material_id)

# 改后
save_run_history(...)
# embed_worldbuilding(material_id)  # 移到 embed_all 统一调用
```

### 步骤5：改引用 - refine.py

**定位**：
```bash
grep -n "embed_outline" src/novel_material/pipeline/refine.py
```

**改动**：
```python
# 改前
embed_outline(material_id)
return True

# 改后
from novel_material.pipeline.embed_all import embed_all
embed_all(material_id)  # 统一调用
return True
```

### 步骤6：改引用 - analyze.py

**定位**：
```bash
grep -n "embed_chapters" src/novel_material/pipeline/analyze.py
```

**改动**：
```python
# 改前（在分析完成后调用）
embed_chapters(material_id)

# 改后（移到 embed_all 统一调用）
# embed_chapters(material_id)  # 注释掉
```

**注意**：章节向量需要特殊处理。analyze 完成后立即生成向量是合理的（后续阶段依赖）。需要设计：
- analyze.py 保留 `embed_chapters()` 调用
- `embed_all()` 检测已存在向量则跳过

### 步骤7：验证

```bash
# 运行完整流水线
nm pipeline full test_novel.txt
# 检查 run_history.yaml 是否有"向量化"阶段记录
grep "向量化" data/novels/nm_xxx/run_history.yaml
```

---

## 批次4：进度检测完善

### 目标

progress.py 添加向量文件检查。

### 步骤1：修改 progress.py

**定位**：
```bash
grep -n "def get_pipeline_progress" src/novel_material/pipeline/progress.py
```

**改动**：添加向量检查字段。
```python
# 改前
return {
    "characters": (novel_dir / "characters" / "_index.yaml").exists(),
    ...
}

# 改后
return {
    "characters": (novel_dir / "characters" / "_index.yaml").exists(),
    "characters_embedded": (novel_dir / "characters" / "character_embeddings.npz").exists(),
    "worldbuilding": (novel_dir / "worldbuilding" / "_index.yaml").exists(),
    "worldbuilding_embedded": (novel_dir / "worldbuilding" / "wb_embeddings.npz").exists(),
    "outline": (novel_dir / "outline" / "_index.yaml").exists(),
    "outline_embedded": (novel_dir / "outline" / "outline_embeddings.npz").exists(),
    "chapters_embedded": (novel_dir / "chapter_embeddings.npz").exists(),
    ...
}
```

### 步骤2：修改 CLI continue 判断逻辑

**定位**：
```bash
grep -n "if not progress.get" src/novel_material/cli/pipeline.py
```

**改动**：检查包含向量。
```python
# 改前
if not progress.get("characters"):
    generate_characters(...)

# 改后
if not progress.get("characters") or not progress.get("characters_embedded"):
    generate_characters(...)
    # 向量化由 embed_all 处理
```

### 步骤3：验证

```bash
nm pipeline status nm_novel_20260514_l362
# 期望输出包含: chapters_embedded, characters_embedded 等字段
```

---

## 批次5：清理冗余代码

### 目标

删除分散的 embed 调用、统一常量定义。

### 步骤1：删除分散定义

| 文件 | 删除内容 |
|------|----------|
| characters_core.py:372 | `embed_characters(material_id)` |
| worldbuilding.py:271 | `embed_worldbuilding(material_id)` |
| refine.py:203 | `embed_outline(material_id)` |

**注意**：保留 analyze.py:599 的 `embed_chapters()`（分析后立即需要）。

### 步骤2：统一历史记录常量

**定位**：
```bash
grep -n "CHARACTERS_STAGES\|WORLDBUILDING_STAGES\|OUTLINE_STAGES\|EVALUATION_STAGES" src/novel_material/pipeline/progress.py
```

**改动**：调整阶段数定义。
```python
# 改前
CHARACTERS_STAGES = 4  # 核心/配角/次要/向量化

# 改后
CHARACTERS_STAGES = 3  # 核心/配角/次要（向量化单独阶段）
```

### 步骤3：验证

```bash
# 全量测试
nm pipeline full test.txt
nm pipeline status <material_id>
# 检查所有字段正确
```

---

## 第三部分：删除清单

| 批次 | 删除项 | grep 定位 |
|------|--------|-----------|
| 1 | `indexed` 状态 | `config.py:120` |
| 3 | `embed_characters()` 调用 | `characters_core.py:372` |
| 3 | `embed_worldbuilding()` 调用 | `worldbuilding.py:271` |
| 3 | `embed_outline()` 调用 | `refine.py:203` |
| 5 | 向量化阶段常量调整 | `progress.py:31-34` |

---

## 第四部分：验收标准

### 功能验收

1. **状态流转完整**
   - `nm pipeline full` 完成后 meta.yaml status 为 `finalized`
   - `nm pipeline evaluate` 完成后 status 为 `evaluated`

2. **向量化历史记录**
   - run_history.yaml 包含"向量化"阶段
   - 记录 tokens 消耗

3. **进度检测准确**
   - `nm pipeline status` 显示向量状态
   - 中断后 continue 能检测向量缺失

### 代码验收

1. **分散定义消除**
   ```bash
   grep -rn "embed_characters\|embed_worldbuilding\|embed_outline" src/novel_material/pipeline/*.py
   # 期望: 只有 embed_all.py 和 analyze.py 有调用
   ```

2. **历史记录统一**
   ```bash
   grep -rn "save_run_history\|PipelineRunner" src/novel_material/pipeline/*.py
   # 期望: 所有模块有记录
   ```

---

## 附录：文件改动清单

| 文件 | 批次 | 改动类型 |
|------|------|----------|
| infra/config.py | 1 | 修改 |
| pipeline/evaluate.py | 2 | 修改 |
| pipeline/refine.py | 2, 3 | 修改 |
| pipeline/embed_all.py | 3 | **新建** |
| pipeline/progress.py | 4, 5 | 修改 |
| cli/pipeline.py | 3, 4 | 修改 |
| pipeline/characters_core.py | 3 | 修改 |
| pipeline/worldbuilding.py | 3 | 修改 |

---

## 附录：数据流图

```
入库 (clean)
    ↓
评估 (evaluated) ← 批次2补状态
    ↓
分析 (analyzed) → embed_chapters（保留）
    ↓
大纲
    ↓
世界观
    ↓
人物
    ↓
标签
    ↓
精调 (finalized) ← 批次2补状态
    ↓
embed_all ← 批次3新增统一入口
    ↓
完成（向量全生成）
```