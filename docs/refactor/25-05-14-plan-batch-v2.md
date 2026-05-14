# 第二轮重构：批次计划

## 项目背景

**项目名称**：novel-material（小说素材处理系统）

**项目目标**：对小说原文进行分析、提取大纲、人物、世界观、标签等素材，生成 YAML 格式的结构化数据。

**当前架构问题**：
1. **缺少单一数据源**：提示词、校验阈值分散在代码各处
2. **全局单例泛滥**：20个文件的 `logger = get_pipeline_logger()` 模块级初始化
3. **基础设施渗透业务逻辑**：yaml.safe_load 调用分散在85处
4. **模块职责混乱**：analyze_utils.py 505行包含5种职责
5. **参数过多**：call_llm 8个参数、build_sliding_window_context 6个参数
6. **配置双入口**：get_settings() 和 load_config() 两个配置函数

**重构目标**：
- 建立契约层：schema/fields.yaml 和 prompts/*.yaml 作为单一数据源
- 建立服务层：ExecutionContext 统一携带 logger、paths、progress、config
- 拆分大模块：按职责分离

**目录结构**：
```
src/novel_material/
├── cli/              # CLI 入口
├── infra/            # 基础设施（config、llm、progress）
├── pipeline/         # 流水线模块（analyze、outline、characters等）
├── storage/          # 数据库同步
├── validation/       # 校验模块
└── tags/             # 标签系统
```

---

## 核心执行原则（Agent 必须遵守）

### 原则一：敢于删除，不要小心翼翼

**删除比保留好。** 有问题的代码直接删，不要留"兼容层"、"过渡函数"。

### 原则二：改完验证，失败就修，不回退

测试失败 → 修复代码让它符合新架构，不是回退改动让新架构妥协。

### 原则三：不留尾巴

每个批次必须完整执行，不留"TODO"、"后续优化"、"临时方案"。

---

## 执行策略（每个批次必须遵守）

**顺序：先建 → 改代码引用 → 验证 → 删除旧代码**

```
步骤1：新建文件/新代码（旧代码不动）
步骤2：修改现有代码引用新文件/新代码（新旧共存）
步骤3：验证通过（python -m pytest tests/）
步骤4：删除旧代码（此时新代码已接管）
```

**绝对不能先删再建。**

---

## 批次总览

```
批次1 → 批次2 → 批次8 → 批次3 → 批次4 → 批次5 → 批次6 → 批次7 → 批次9 → 批次10 → 批次11
(契约层) (服务层) (参数层) (改造层) (拆分层) (清理层) (验证层) (注释层) (配置层) (命名层) (进度层)
```

**依赖关系**：
- 批次1-2 必须先完成（契约和服务基础设施）
- **批次8 必须在批次3之前**：批次8新建参数对象类，批次3-4的函数才能使用
- 批次7 在批次5 之后
- **批次9 在批次2 之后**：ExecutionContext 已建立，改用 load_app_config

---

## 批次1：建立契约层（schema + prompts）

### 目标

建立单一数据源，消除提示词、校验阈值分散定义的问题。

### 步骤1：新建契约文件

#### 1.1 创建 `schema/fields.yaml`

**作用**：所有校验阈值的唯一来源，修改此文件自动同步到提示词、schema.py、quality.py。

**关键字段示例**：

```yaml
# 字段契约
summary:
  description: 章节摘要
  min_length: 50
  max_length: 100
  validate_in: ["prompt", "schema", "quality"]

key_event:
  description: 关键事件描述
  min_length: 10
  max_length: 30

# 非字段阈值（常量统一）
character_thresholds:
  core: 50
  supporting: 10
  minor: 5

sample_threshold: 200
avg_tokens_per_entry: 40
```

**注意**：
- `validate_in` 指定哪些地方需要校验（prompt/schema/quality）
- 非字段阈值（如 character_thresholds）也放在此文件统一管理

#### 1.2 创建 `schema/__init__.py`

**导出**：`FieldSchema`, `load_field`, `get_threshold`

#### 1.3 创建 `schema/fields_loader.py`

**核心函数**：
- `FieldSchema.load(field_name)` → 返回字段契约（包含 min_length/max_length）
- `FieldSchema.load_all()` → 返回所有字段契约

**关键逻辑**：从 fields.yaml 读取，只加载有 `validate_in` 的字段。

#### 1.4 创建 `schema/thresholds.py`

**核心函数**：
- `get_threshold(threshold_name)` → 返回阈值值（如 `get_threshold("character_thresholds")["core"]`）

#### 1.5 创建 `prompts/*.yaml`（共5个）

**文件列表**：
- `prompts/analyze.yaml` — 章级分析提示词
- `prompts/outline.yaml` — 大纲生成提示词（包含 premise_prompt/acts_prompt/beats_prompt）
- `prompts/characters.yaml` — 人物提取提示词（包含 core_prompt/supporting_prompt/minor_prompt）
- `prompts/worldbuilding.yaml` — 世界观提示词
- `prompts/evaluate.yaml` — 评估提示词

**关键结构**：

```yaml
system_prompt: |
  你是专业的小说分析助手...

output_schema: |
  {
    "summary": "章节摘要",
    ...
  }
```

#### 1.6 创建 `prompts/__init__.py`

**导出**：`Prompt`, `load_prompt`

#### 1.7 创建 `prompts/prompt_loader.py`

**核心函数**：
- `Prompt.load(prompt_name)` → 返回提示词（包含 system_prompt/output_schema）
- **模板变量替换**：`{{summary_min}}` → 从 FieldSchema.load("summary").min_length 获取

### 步骤2：修改代码引用契约

#### 2.1 修改 `validation/schema.py`

**改前**：
```python
summary: str = Field(..., min_length=40, max_length=500)
```

**改后**：
```python
SUMMARY_SCHEMA = FieldSchema.load("summary")
summary: str = Field(..., min_length=SUMMARY_SCHEMA.min_length, max_length=SUMMARY_SCHEMA.max_length)
```

#### 2.2 修改 `validation/quality.py`

**改前**：
```python
if len(summary) < 40:
```

**改后**：
```python
SUMMARY_SCHEMA = FieldSchema.load("summary")
if len(summary) < SUMMARY_SCHEMA.min_length:
```

#### 2.3 修改 `pipeline/characters_stats.py`

**改前**：
```python
CHARACTER_THRESHOLDS = {"core": 50, "supporting": 10, "minor": 5}
_SAMPLE_THRESHOLD = 200
```

**改后**：
```python
CHARACTER_THRESHOLDS = get_threshold("character_thresholds")
_SAMPLE_THRESHOLD = get_threshold("sample_threshold")
```

#### 2.4 修改 `pipeline/loader.py` 和 `pipeline/evaluate.py`

**删除重复定义**：
- loader.py 的 `_SAMPLE_THRESHOLD = 200` → 改用 `get_threshold("sample_threshold")`
- loader.py 的 `_AVG_TOKENS_PER_ENTRY = 40` → 改用 `get_threshold("avg_tokens_per_entry")`
- evaluate.py 的 `_SAMPLE_THRESHOLD = 200` → 删除，已从契约加载

#### 2.5 修改提示词使用文件

**涉及文件**：analyze_utils.py、outline_core.py、outline_beats.py、characters_layer.py、worldbuilding.py、evaluate.py

**改前**：内联 `system_prompt = """..."""`

**改后**：
```python
prompt = load_prompt("analyze")
result = call_llm(prompt.system_prompt, user_prompt, config)
```

### 步骤3：验证

```bash
python -c "from novel_material.schema import FieldSchema; print(FieldSchema.load('summary').min_length)"
# 预期: 50

python -c "from novel_material.schema import get_threshold; print(get_threshold('character_thresholds')['core'])"
# 预期: 50

python -m pytest tests/
```

### 步骤4：删除旧代码

**删除清单**：

| 删除特征 | 文件 | 定位方式 |
|----------|------|---------|
| `_SYSTEM_PROMPT` 常量定义 | analyze_utils.py | grep 找到后删除 |
| `_CHAPTER_JSON_SCHEMA` 常量定义 | analyze_utils.py | grep 找到后删除 |
| `_BATCH_JSON_SCHEMA` 常量定义 | analyze_utils.py | grep 找到后删除 |
| `_SYSTEM_PROMPT` 常量定义 | evaluate.py | grep 找到后删除 |
| 内联 `system_prompt_premise` | outline_core.py | grep 找到后删除 |
| 内联 `system_prompt` | outline_beats.py | grep 找到后删除 |
| 内联 `system_prompt` | worldbuilding.py | grep 找到后删除 |
| 内联 `system_prompt`（3处） | characters_layer.py | grep 找到后删除所有 |

---

## 批次2：建立服务层（ExecutionContext + yaml_io + path_service）

### 目标

建立统一的基础设施服务层，消除全局单例、分散的 yaml 调用。

### 步骤1：新建服务文件

#### 2.1 创建 `infra/yaml_io.py`

**核心函数**：
- `load_yaml(path)` → 返回字典，文件不存在返回空字典
- `save_yaml(path, data)` → 写入 YAML
- `load_yaml_list(path)` → 返回列表

**关键逻辑**：统一编码 utf-8，统一错误处理。

#### 2.2 创建 `infra/path_service.py`

**核心函数**（PathService 类）：
- `novel_dir(material_id)` → 素材目录
- `meta_path(material_id)` → meta.yaml 路径
- `chapters_path(material_id)` → chapters.yaml 路径
- `chapters_dir(material_id)` → chapters/ 目录
- `outline_dir(material_id)` → outline/ 目录
- `characters_dir(material_id)` → characters/ 目录
- `evaluation_path(material_id)` → evaluation.yaml 路径

#### 2.3 创建 `infra/progress_manager.py`

**核心类**：ProgressManager

**核心函数**：
- `register_stage(name, total)` → 注册阶段，返回阶段索引
- `update(stage_idx, done, desc)` → 更新进度

#### 2.4 创建 `infra/logging_service.py`

**核心函数**：
- `create_logger(material_id, log_file)` → 创建素材专属 logger

#### 2.5 创建 `infra/context.py`

**核心类**：ExecutionContext

**字段**：material_id、logger、paths、progress、config

**核心函数**：
```python
@classmethod
def create(cls, material_id, log_file=None, progress_callback=None, config=None):
    logger = create_logger(material_id, log_file)
    paths = PathService()
    progress = ProgressManager(update_callback=progress_callback)
    config = config or load_config()
    return cls(material_id, logger, paths, progress, config)
```

### 步骤2：修改代码使用服务层

#### 2.1 修改 pipeline 函数签名

**改前**：
```python
def generate_outline(material_id: str, progress_callback=None, provider=None):
    logger = get_pipeline_logger()
    novel_dir = NOVELS_DIR / material_id
```

**改后**：
```python
def generate_outline(ctx: ExecutionContext):
    novel_dir = ctx.paths.novel_dir(ctx.material_id)
    ctx.logger.info("...")
    ctx.progress.update(0, 0, "开始")
```

**CLI 调用适配**：

```python
# 改前
def cmd_outline(material_id: str):
    progress_callback = create_progress_callback()
    generate_outline(material_id, progress_callback=progress_callback)

# 改后
def cmd_outline(material_id: str):
    ctx = ExecutionContext.create(material_id, progress_callback=create_progress_callback())
    generate_outline(ctx)
```

**涉及文件**：
- pipeline/analyze.py、outline.py、worldbuilding.py、characters.py、tags.py、refine.py、evaluate.py
- cli/pipeline.py（创建 ctx）

#### 2.2 修改 yaml 调用

**改前**：
```python
with open(novel_dir / "meta.yaml", "r") as f:
    meta = yaml.safe_load(f)
```

**改后**：
```python
meta = load_yaml(ctx.paths.meta_path(ctx.material_id))
```

#### 2.3 修改路径调用

**改前**：
```python
novel_dir = NOVELS_DIR / material_id
```

**改后**：
```python
novel_dir = ctx.paths.novel_dir(ctx.material_id)
```

#### 2.4 修改 storage/sync_utils.py

**改前**：
```python
DATABASE_URL = os.getenv("DATABASE_URL")  # 模块级初始化

def get_db_connection():
    if not DATABASE_URL:
        raise DatabaseConfigError("DATABASE_URL 未设置")
```

**改后**：
```python
def get_db_connection(database_url: str | None = None):
    from novel_material.infra.config_service import load_app_config
    effective_url = database_url or load_app_config().get("database_url")
    if not effective_url:
        raise DatabaseConfigError("DATABASE_URL 未设置")
```

### 步骤3：验证

```bash
python -c "from novel_material.infra.yaml_io import load_yaml; print('yaml_io OK')"
python -c "from novel_material.infra.context import ExecutionContext; ctx = ExecutionContext.create('test'); print(ctx.material_id)"

python -m pytest tests/
```

### 步骤4：删除旧参数和全局变量

**删除清单**：

| 删除特征 | 文件范围 | 定位方式 |
|----------|---------|---------|
| `logger = get_pipeline_logger()` 模块级初始化 | pipeline 模块（14个文件）、infra 模块（3个）、cli 模块（1个）、storage 模块（1个） | grep 找到后删除整行 |
| `progress_callback` 参数定义 | 所有 pipeline 函数 | grep 找到后删除参数 |
| `provider` 参数定义 | 所有 pipeline 函数 | grep 找到后删除参数 |
| `DATABASE_URL = os.getenv(...)` | sync_utils.py | grep 找到后删除整行 |
| `logger` 在 `__all__` 导出 | sync_utils.py | 删除导出项 |

---

## 批次3：改造 yaml 和路径调用（85处）

### 目标

消除所有 yaml.safe_load 和 yaml.dump 的分散调用。

### 步骤1：无新建（服务已在批次2建好）

### 步骤2：替换所有 yaml 调用

**替换模式**：

```python
# 改前
with open(path, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

# 改后
data = load_yaml(path)

# 改前
with open(path, "w", encoding="utf-8") as f:
    yaml.dump(data, f, allow_unicode=True)

# 改后
save_yaml(path, data)
```

**文件分布**：
- pipeline/*.py：~40处
- storage/*.py：~20处
- validation/*.py：~15处
- cli/*.py：~10处
- 其他：~10处

### 步骤3：验证

```bash
python -m pytest tests/

# 检查残留
grep -r "yaml.safe_load" src/novel_material/
grep -r "yaml.dump" src/novel_material/
# 应返回空
```

---

## 批次4：拆分大模块（职责分离）

### 目标

拆分职责混乱的大模块：analyze_utils.py、outline_core.py、validation/schema.py。

### 步骤1：新建拆分后的模块

#### 4.1 从 analyze_utils.py 提取

**新建文件**：
- `pipeline/analyze_validators.py` — 校验函数（纯逻辑，无IO）
- `pipeline/analyze_files.py` — 文件操作（只做IO）
- `pipeline/analyze_temperature.py` — 动态温度控制（独立算法）

#### 4.2 从 outline_core.py 提取

**新建文件**：
- `pipeline/outline_logic.py` — 业务逻辑（无IO）
- `pipeline/outline_io.py` — 文件读写（只做IO）

#### 4.3 从 validation/schema.py 提取

**新建文件**：
- `validation/models.py` — Pydantic 模型定义（无IO）
- `validation/validators.py` — 校验函数（输入数据，返回错误）

### 步骤2：修改导入路径

**改前**：
```python
from novel_material.pipeline.analyze_utils import validate_chapter_analysis
```

**改后**：
```python
from novel_material.pipeline.analyze_validators import validate_chapter_analysis
```

### 步骤3：验证

```bash
python -m pytest tests/
```

### 步骤4：删除原文件或缩减

| 删除目标 | 文件 | 操作 |
|----------|------|------|
| 整个文件 | pipeline/analyze_utils.py | 删除（已拆分到3个新文件） |
| 大部分代码 | pipeline/outline_core.py | 只保留入口函数 generate_outline(ctx)（不超过50行） |
| Pydantic 模型和校验函数 | validation/schema.py | 只保留入口函数 validate_material(ctx) |

---

## 批次5：清理遗留垃圾

### 目标

删除遗留的无用类、空壳文件。

### 步骤4：删除遗留代码和文件

| 删除目标 | 文件 | 定位方式 |
|----------|------|---------|
| 整个文件 | infra/constants.py | 如果存在则删除 |
| class SilentConsole | infra/progress.py | grep 找到后删除类定义 |
| class PipelineLogger | infra/progress.py | grep 找到后删除类定义 |
| class StageTracker | infra/progress.py | grep 找到后删除类定义 |
| class PipelineRunner | infra/progress.py | grep 找到后删除类定义 |
| 空壳文件 | pipeline/outline.py | 删除，改用导入 outline_logic |
| 空壳文件 | pipeline/characters.py | 删除，改用导入 characters_core |

---

## 批次6：验证整体效果

### 目标

验证所有重构完成，确保旧代码消失。

### 验证场景

```bash
# 契约加载
python -c "from novel_material.schema import FieldSchema; print(FieldSchema.load('summary').min_length)"

# ExecutionContext 使用
python -c "from novel_material.infra.context import ExecutionContext; ctx = ExecutionContext.create('test'); print(ctx.paths.novel_dir('test'))"

# 测试
python -m pytest tests/

# 旧代码消失检查
grep -r "yaml.safe_load" src/novel_material/      # 空
grep -r "logger = get_pipeline_logger" src/novel_material/  # 空
grep -r "_SYSTEM_PROMPT" src/novel_material/      # 空
```

---

## 批次7：注释清理

### 目标

删除冗余注释，补充缺失注释。

### 步骤2：删除冗余注释

| 删除目标 | 文件 | 定位方式 |
|----------|------|---------|
| "# 第X层：XXX" | characters_core.py | grep 找到后删除（代码已表达） |
| "# 第一步/第二步" | 其他文件 | grep 找到后删除流程注释 |

### 步骤3：补充缺失注释

| 补充目标 | 文件 | 补充内容 |
|----------|------|---------|
| 阈值来源 | schema/fields.yaml | 补充 "# 为什么是这个值：实测数据" |
| 返回空列表原因 | loader.py | 补充 "# 返回空列表而非抛异常：允许调用方优雅处理" |

---

## 批次8：函数参数重构

### 目标

将参数过多的函数改用对象封装，为批次3-4做准备。

### 步骤1：新建参数对象类

#### 8.1 创建 `pipeline/analyze_context.py`

**新建文件**（不是修改 analyze_utils.py，因为 analyze_utils.py 在批次4删除）。

**核心类**：SlidingWindowContextArgs

**字段**：chapter_num、chapters_data、lines、chapter_index、evaluation、next_preview_chars

**核心函数**：`build_sliding_window_context(args)` → 逻辑从 analyze_utils.py 移入

#### 8.2 创建 `infra/llm_args.py`

**核心类**：LLMCallArgs

**字段**：system_prompt、user_prompt、config、max_tokens_override 等8个参数

#### 8.3 创建 `pipeline/loader_args.py`

**核心类**：AnalysisContextArgs

**字段**：novel_dir、config、chapters_data、material_id、summary_tokens_key、fallback_chars

### 步骤2：修改函数签名

**改前**（call_llm 8个参数）：
```python
def call_llm(system_prompt, user_prompt, config, max_tokens_override=None, ...):
```

**改后**：
```python
def call_llm(args: LLMCallArgs):
    system_prompt = args.system_prompt
    ...
```

**注意**：outline_core.py 直接调用 `build_summary_pool` 而不是 `build_analysis_context`，需统一改用 `build_analysis_context`。

### 步骤3：修改调用方

**改前**：
```python
result = call_llm(system_prompt, user_prompt, config)
```

**改后**：
```python
args = LLMCallArgs(system_prompt=system_prompt, user_prompt=user_prompt, config=config)
result = call_llm(args)
```

### 步骤4：验证

```bash
python -m pytest tests/
```

**注意**：批次8只新建参数对象类，不删除旧函数。旧函数删除在批次4执行。

---

## 批次9：配置合并

### 目标

统一 get_settings() 和 load_config() 为单一入口。

### 步骤1：新建 `infra/config_service.py`

**核心函数**：`load_app_config(provider)` → 合并 settings.yaml 和 providers.yaml

### 步骤2：修改调用方

#### 9.1 修改 ExecutionContext.create

**改前**（批次2）：
```python
from novel_material.infra.llm import load_config
effective_config = config or load_config()
```

**改后**：
```python
from novel_material.infra.config_service import load_app_config
effective_config = config or load_app_config()
```

#### 9.2 修改其他调用方

**改前**：
```python
from novel_material.infra.config import get_settings
settings = get_settings()
```

**改后**：
```python
from novel_material.infra.config_service import load_app_config
config = load_app_config()
```

### 步骤3：验证

```bash
python -m pytest tests/
```

### 步骤4：删除旧配置函数

| 删除目标 | 文件 | 操作 |
|----------|------|------|
| get_settings() | infra/config.py | 删除函数 |
| load_config() | infra/llm.py | 删除函数 |

---

## 批次10：私有命名规范统一

### 目标

统一私有函数命名，私有函数不应出现在 `__all__`。

### 步骤2：修改命名

| 文件 | 函数 | 改动 |
|------|------|------|
| analyze_utils.py | validate_chapter_analysis | 加 `_` 前缀（仅内部使用） |

### 步骤3：修改 `__all__`

**改前**（outline_temp.py）：
```python
__all__ = ["_save_acts_temp", "_load_acts_temp", ...]
```

**改后**：
```python
__all__ = []  # 私有函数不应导出
```

---

## 批次11：进度阶段统一管理

### 目标

消除 total 值分散在 5+ 个文件的问题。

### 步骤2：修改进度定义方式

**改前**（cli/pipeline.py）：
```python
def cmd_characters(material_id):
    total = 4
    progress_callback(0, total, "核心人物")
```

**改后**：
```python
ctx = ExecutionContext.create(material_id)
ctx.progress.register_stage("核心人物", total=None)
ctx.progress.register_stage("配角", total=None)
ctx.progress.register_stage("次要人物", total=None)
ctx.progress.register_stage("向量化", total=1)
generate_characters(ctx)
```

### 步骤3：删除分散的 total 定义

| 删除目标 | 文件范围 |
|----------|---------|
| `total=4` 等硬编码 | cli/pipeline.py 各 cmd 函数 |
| `total_stages=4` 等 | characters_core.py、outline_core.py、evaluate.py |

---

## 附录：新建文件清单（27个）

| 文件路径 | 批次 |
|----------|------|
| schema/fields.yaml | 批次1 |
| schema/__init__.py | 批次1 |
| schema/fields_loader.py | 批次1 |
| schema/thresholds.py | 批次1 |
| prompts/__init__.py | 批次1 |
| prompts/prompt_loader.py | 批次1 |
| prompts/analyze.yaml | 批次1 |
| prompts/outline.yaml | 批次1 |
| prompts/characters.yaml | 批次1 |
| prompts/worldbuilding.yaml | 批次1 |
| prompts/evaluate.yaml | 批次1 |
| infra/yaml_io.py | 批次2 |
| infra/path_service.py | 批次2 |
| infra/progress_manager.py | 批次2 |
| infra/logging_service.py | 批次2 |
| infra/context.py | 批次2 |
| pipeline/analyze_context.py | 批次8 |
| infra/llm_args.py | 批次8 |
| pipeline/loader_args.py | 批次8 |
| infra/config_service.py | 批次9 |
| pipeline/analyze_validators.py | 批次4 |
| pipeline/analyze_files.py | 批次4 |
| pipeline/analyze_temperature.py | 批次4 |
| pipeline/outline_logic.py | 批次4 |
| pipeline/outline_io.py | 批次4 |
| validation/models.py | 批次4 |
| validation/validators.py | 批次4 |

## 附录：删除文件清单（3个）

| 文件路径 | 批次 |
|----------|------|
| pipeline/analyze_utils.py | 批次4 |
| infra/constants.py | 批次5 |
| pipeline/outline.py（空壳） | 批次5 |

## 附录：执行检查清单

每个批次完成后：

```bash
# 1. 测试通过
python -m pytest tests/

# 2. 导入检查
python -c "from novel_material.schema import FieldSchema; print(FieldSchema.load('summary'))"
python -c "from novel_material.infra.context import ExecutionContext; print(ExecutionContext.create('test'))"

# 3. 旧代码消失检查
grep -r "yaml.safe_load" src/novel_material/
grep -r "logger = get_pipeline_logger" src/novel_material/
```