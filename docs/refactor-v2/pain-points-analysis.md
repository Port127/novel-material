# 四大痛点深度分析

## 痛点1：CLI进度条——打地鼠式调试

### 问题现象

你说"修了这个问题，另外一个问题又冒出来"，根源是：

**进度数据分散在5+个文件，每个文件自己定义 total 值**

| 文件 | 定义位置 | total值 |
|------|----------|---------|
| `cli/pipeline.py:244` | `cmd_characters` | `total=4` |
| `cli/pipeline.py:166` | `cmd_evaluate` | `total=5` |
| `cli/pipeline.py:195` | `cmd_outline` | `total=None`（不确定） |
| `cli/pipeline.py:128` | `cmd_analyze` | 动态计算 `range_total` |
| `characters_core.py:85` | `PipelineRunner` | `total_stages=4` |
| `characters_core.py:141` | `progress_callback` 循环 | `total_batches=3` |
| `outline_core.py:89` | `PipelineRunner` | `total_stages=3` |
| `evaluate.py:382` | `PipelineRunner` | `total_stages=5` |

### 为什么是打地鼠

**场景：你想在人物提取前加一个"预处理"阶段**

需要改动：
1. `cli/pipeline.py:244` → 改 `total=4` 为 `total=5`
2. `characters_core.py:85` → 改 `total_stages=4` 为 `total_stages=5`
3. `characters_core.py:141` → 改 `total_batches=3` 为 `total_batches=4`
4. `characters_core.py` → 在循环中加一个 `progress_callback(..., ...)`
5. `cli/pipeline.py:cmd_full` → 改人物阶段的 `total=4` 为 `total=5`
6. `cli/pipeline.py:cmd_continue` → 同上

**改了6个文件，漏了一个就会出问题**

### 设计缺陷

```python
# 当前设计：每个函数自己管理进度
def generate_characters(material_id, progress_callback=None):
    total_batches = 3  # 自己定义 total
    progress_callback(0, total_batches, "...")
    progress_callback(1, total_batches, "...")
    ...

# 问题：
# 1. progress_callback 签名不一致（有的用 done/total，有的用 stage_num/total_stages）
# 2. total 值是"魔法数字"，分散在各处
# 3. CLI 和 Pipeline 都定义 total，两边不一致就会出问题
```

### 应该怎么设计

```python
# 方案：进度统一管理，而不是每个函数自己算

class ProgressManager:
    """统一的进度管理器"""

    def __init__(self):
        self.stages: list[StageInfo] = []

    def register_stage(self, name: str, total: int | None = None):
        """注册阶段（而不是在代码里写 total=4）"""
        self.stages.append(StageInfo(name, total))

    def update(self, stage_idx: int, done: int, total: int, desc: str):
        """统一更新接口"""
        ...

# 使用：
progress = ProgressManager()
progress.register_stage("核心人物", None)
progress.register_stage("配角", None)
progress.register_stage("次要", None)
progress.register_stage("向量化", 1)

# pipeline 函数不自己定义 total，只调用 update
def generate_characters(material_id, progress: ProgressManager):
    progress.update(0, len(core), total_core, f"提取核心人物 {len(core)} 人")
```

---

## 痛点2：日志——同样的打地鼠问题

### 问题现象

**改日志格式/输出方式，要改24个文件的 `logger = get_pipeline_logger()`**

不仅如此：

```python
# infra/progress.py 中有多个日志相关类
SilentConsole       # 禁止控制台输出
PipelineLogger      # 流水线日志
StageTracker        # 阶段追踪（也写日志）
PipelineRunner      # 运行记录（也写日志）

# 每个类都有自己的日志逻辑
# 改日志格式 → 要看4个类 + 24个文件
```

### 设计缺陷

```python
# 当前：模块级初始化，无法定制
logger = get_pipeline_logger()  # import时就初始化

# 问题：
# 1. 所有模块共享同一个 logger
# 2. 无法按 material_id 区分日志文件（当前靠 PID 隔离）
# 3. 无法在测试中 mock
# 4. SilentConsole 是全局开关，改了影响所有模块
```

### 应该怎么设计

```python
# 方案：日志作为上下文的一部分，而不是全局单例

class ExecutionContext:
    """执行上下文，携带 logger、progress、config"""

    logger: Logger
    progress: ProgressManager
    material_id: str

# 所有函数接收 context
def generate_outline(ctx: ExecutionContext):
    ctx.logger.info(f"[{ctx.material_id}] 开始生成大纲")

# CLI 创建 context
ctx = ExecutionContext(
    logger=create_logger(material_id, log_file),
    progress=ProgressManager(),
    material_id=material_id,
)
generate_outline(ctx)
```

---

## 痛点3：提示词——分散在7+个文件，难以审查

### 问题现象

| 文件 | 提示词定义 | 形式 |
|------|-----------|------|
| `analyze_utils.py:22-44` | `_SYSTEM_PROMPT` | 模块级常量 |
| `analyze_utils.py:47-60` | `_CHAPTER_JSON_SCHEMA` | 模块级常量 |
| `evaluate.py:14-38` | `_SYSTEM_PROMPT` | 模块级常量（另一个版本） |
| `outline_core.py:133-148` | `system_prompt_premise` | **函数内局部变量** |
| `outline_beats.py:14-22` | `system_prompt` | **函数内局部变量** |
| `worldbuilding.py:73-87` | `system_prompt` | **函数内局部变量** |
| `characters_layer.py:26-42` | `system_prompt` | **函数内局部变量（3个版本）** |
| `tags.py` | `build_system_prompt()` | 动态生成函数 |

### 为什么难审查

**场景：你想改"摘要长度"的描述**

```python
# analyze_utils.py:23
summary：章节摘要，50-100字

# 但校验用的阈值是 40 字，不是 50 字
# validation/quality.py:266
if len(summary) < 40:  # ← 不一致！

# 还要检查：
# - outline_core.py 里有没有提到摘要长度？
# - characters_layer.py 里有没有？
# - worldbuilding.py 里有没有？
```

**提示词散落在代码各处，改一个要 grep 全项目**

### 设计缺陷

```python
# 当前：提示词和代码混在一起
def generate_outline(...):
    # 第133行：提示词内联在代码里
    system_prompt_premise = """你是专业的小说结构分析师...
    {
      "premise": "一句话核心前提（50字以内）",
      ...
    }"""

    # 第152行：调用 LLM
    result = call_llm(system_prompt_premise, ...)
```

**问题**：
- 改提示词要改代码文件
- 无法单独审查提示词（没有提示词文件）
- 提示词版本管理困难（代码 git 和提示词 git 混在一起）

### 应该怎么设计

```python
# 方案：提示词独立文件，代码只引用

# prompts/
#   analyze.yaml        # 章级分析提示词
#   outline.yaml        # 大纲生成提示词
#   characters.yaml     # 人物提取提示词
#   worldbuilding.yaml  # 世界观提示词

# prompts/analyze.yaml
system_prompt: |
  你是专业的小说分析助手...

output_schema:
  summary:
    description: 章节摘要
    min_length: 50
    max_length: 100

# 代码：
from novel_material.infra.prompts import load_prompt

prompt = load_prompt("analyze")
result = call_llm(prompt.system_prompt, user_prompt, config)
```

**好处**：
- 提示词可以单独审查（yaml 文件）
- 改提示词不改代码
- 提示词和校验阈值可以统一管理（都在 yaml 里）

---

## 痛点4：校验与定义不一致——改哪里？

### 问题现象：摘要长度

**提示词说：50-100字**

```python
# analyze_utils.py:23（提示词模板）
1. summary：章节摘要，50-100字

# analyze_utils.py:47（JSON 示例）
"summary": "章节摘要，50-100字"
```

**校验用：40字（正文）**

```python
# validation/quality.py:266
if len(summary) < 40:
    errors.append(f"第{ch_num}章: 摘要过短（{len(summary)}字，要求 ≥40）")

# validation/quality.py:262（特殊类型）
if len(summary) < 20:

# validation/schema.py:74
summary: str = Field(..., min_length=40, max_length=500)

# analyze_utils.py:401（校验函数）
if len(summary) < 40:
    errors.append(f"章节{ch_num}: 摘要过短({len(summary)}字)")
```

**到底改哪里？**
- 提示词改？→ 改 `analyze_utils.py:23`
- quality.py 改？→ 改 `validation/quality.py:266`
- schema.py 改？→ 改 `validation/schema.py:74`
- analyze_utils.py 校验改？→ 改 `analyze_utils.py:401`

**改了提示词，校验阈值可能还是旧值**
**改了校验阈值，提示词可能还是旧值**

### 其他不一致项

| 字段 | 提示词定义 | schema.py 定义 | quality.py 定义 |
|------|-----------|---------------|-----------------|
| summary | 50-100字 | min=40, max=500 | <40报错 |
| key_event | 10-30字 | max=100 | 无校验 |
| emotion_transition | 10-50字 | max=100 | <5报错 |
| plot_progress | 20-100字 | max=200 | <10报错 |
| arc_summary | 50字 | 无定义 | 无校验 |

### 设计缺陷

**校验阈值分散在3个地方，没有统一来源**

```python
# 1. 提示词模板（analyze_utils.py）
summary：章节摘要，50-100字

# 2. Pydantic 模型（validation/schema.py）
summary: str = Field(..., min_length=40, max_length=500)

# 3. 质量检查（validation/quality.py）
if len(summary) < 40: ...
```

**问题**：
- 改提示词 → 不知道校验阈值要不要改
- 改校验阈值 → 不知道提示词要不要改
- 没有统一的"数据契约"

### 应该怎么设计

```python
# 方案：统一的数据契约文件

# schema/
#   chapter_fields.yaml  # 所有字段的定义和约束

# chapter_fields.yaml
summary:
  description: 章节摘要
  min_length: 50    # 提示词和校验都用这个值
  max_length: 100
  validate_in: ["prompt", "schema", "quality"]  # 哪些地方要校验

key_event:
  description: 关键事件描述
  min_length: 10
  max_length: 30

# 代码：
from novel_material.schema import FieldSchema

summary_schema = FieldSchema.load("summary")

# 提示词模板使用
prompt = f"summary：{summary_schema.description}，{summary_schema.min_length}-{summary_schema.max_length}字"

# Pydantic 模型使用
summary: str = Field(..., min_length=summary_schema.min_length, ...)

# 质量检查使用
if len(summary) < summary_schema.min_length: ...
```

**好处**：
- 改一个 yaml 文件，所有地方自动同步
- 提示词、校验、schema 都是同一个来源
- 审查时看 yaml 文件，不用 grep 代码

---

## 总结：四大痛点的共同根源

| 痛点 | 根源 |
|------|------|
| 进度条 | 数据分散（total值在5+个文件） |
| 日志 | 全局单例（24个文件共享） |
| 提示词 | 代码耦合（散落在7+个文件） |
| 校验阈值 | 定义分散（提示词/schema/quality 三个来源） |

**共同根源：缺少"单一数据源"**

- 进度：应该有 `ProgressManager` 统一管理
- 日志：应该有 `ExecutionContext` 传递
- 提示词：应该有 `prompts/*.yaml` 独立文件
- 校验阈值：应该有 `schema/*.yaml` 统一契约

**一句话**：当前设计是"分散式"，改一处要 grep 全项目；应该改成"集中式"，改一处自动同步。