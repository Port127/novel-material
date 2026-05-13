# 深度审核报告：重构未触及的核心问题

## 一、模块边界模糊

### 1.1 analyze_utils.py：职责混乱的"杂物箱"

**问题**：505行代码包含 5 种不同职责：

```python
# 第19-93行：常量定义（提示词模板）
_SYSTEM_PROMPT = """..."""
_CHAPTER_JSON_SCHEMA = """..."""

# 第99-127行：配置读取辅助函数
def _get_max_chapter_tokens() -> int: ...
def _get_batch_size(config: dict) -> int: ...

# 第133-244行：动态提示词/温度控制
def _build_dynamic_system_prompt(...) -> str: ...
def _should_use_thinking_mode(...) -> int | None: ...

# 第251-370行：校验函数
def validate_window_fields(...) -> list[str]: ...
def validate_chapter_analysis(...) -> list[str]: ...

# 第418-481行：文件操作
def _load_existing_chapters(...) -> dict: ...
def _append_chapter(...) -> None: ...
def _merge_chapters(...) -> None: ...
```

**为什么这是问题**：
- 改提示词格式 → 要改这个文件，但校验逻辑也在这里
- 改文件存储方式 → 要改这个文件，但提示词模板也在这里
- 测试校验逻辑 → 要 mock 整个文件，包括不相关的提示词

**应该怎么拆**：
```
analyze/
├── prompts.py       # 提示词模板（可独立测试、独立修改）
├── validators.py    # 校验逻辑（纯函数，无 IO）
├── file_ops.py      # 文件操作（只做 IO）
├── config.py        # 配置辅助（只读配置）
├── temperature.py   # 动态温度控制（独立算法）
```

---

### 1.2 outline_core.py：业务与基础设施混杂

**问题**：420行代码，一个函数做了所有事：

```python
def generate_outline(material_id, ...):
    # 第57-84行：文件读取（基础设施）
    novel_dir = NOVELS_DIR / material_id
    with open(meta_file, "r") as f: meta = yaml.safe_load(f)
    with open(chapter_index_file, "r") as f: chapter_index = yaml.safe_load(f)

    # 第133-148行：提示词构建（业务逻辑）
    system_prompt_premise = """你是专业的小说结构分析师..."""

    # 第152-164行：LLM 调用（基础设施）
    result = call_llm(system_prompt, user_prompt, config, ...)

    # 第167-176行：文件写入（基础设施）
    with open(meta_file, "w") as f: yaml.dump(meta, f, ...)

    # 第197-240行：断点续传逻辑（业务逻辑）
    acts = _load_acts_temp(outline_dir)
    if acts and ...: logger.info("断点续传...")

    # 第242-338行：循环生成 beats（业务逻辑）
    for act in acts:
        for seq in act.get("sequences", []):
            beats = _generate_beats_for_sequence(...)
```

**为什么这是问题**：
- 改存储格式（yaml → json）→ 要改所有文件操作代码
- 改 LLM 调用方式 → 要改这个函数的中间部分
- 改大纲生成逻辑 → 要在 420 行代码里找到对应位置

**应该怎么拆**：
```python
# 业务层（只处理数据，不碰 IO）
def generate_outline_structure(chapters_data, meta, config) -> OutlineStructure:
    """纯业务逻辑，输入数据，输出结构"""

# 基础设施层（只做 IO）
class OutlineStorage:
    def load_meta(self, material_id) -> dict: ...
    def save_meta(self, material_id, meta) -> None: ...
    def load_temp(self, material_id) -> dict: ...
    def save_temp(self, material_id, acts) -> None: ...

# 入口层（组合调用）
def generate_outline(material_id, config, storage: OutlineStorage):
    meta = storage.load_meta(material_id)
    structure = generate_outline_structure(chapters_data, meta, config)
    storage.save_structure(material_id, structure)
```

---

### 1.3 validation/schema.py：模型与校验混杂

**问题**：554行代码包含 Pydantic 模型定义和校验函数：

```python
# 第27-196行：Pydantic 模型定义
class MetaModel(BaseModel): ...
class ChapterEntryModel(BaseModel): ...
class EvaluationModel(BaseModel): ...

# 第201-546行：校验函数（直接操作文件）
def validate_meta(material_id) -> list[str]:
    meta_file = NOVELS_DIR / material_id / "meta.yaml"  # 路径操作
    with open(meta_file, "r") as f: data = yaml.safe_load(f)  # 文件操作
    try: MetaModel(**{k: data.get(k) for k in ...})  # 模型校验
```

**为什么这是问题**：
- Pydantic 模型是"数据契约"，应该独立、稳定
- 校验函数是"数据访问 + 校验"，包含了文件操作
- 改路径 → 要改校验函数
- 改模型 → 要改同一个文件

**应该怎么拆**：
```python
# models.py（纯数据契约，无 IO）
class MetaModel(BaseModel): ...
class ChapterEntryModel(BaseModel): ...

# validators.py（纯校验逻辑，输入数据）
def validate_meta_dict(data: dict) -> list[str]:
    """输入字典，返回错误"""
    try: MetaModel(**data)
    except PydanticValidationError: ...

# schema_loader.py（只做 IO）
def load_meta(material_id) -> dict:
    return yaml.safe_load(NOVELS_DIR / material_id / "meta.yaml")
```

---

## 二、注释问题：解释"做什么"而非"为什么"

### 2.1 冗余注释

```python
# analyze_utils.py:99-108
def _fmt_duration(sec: float) -> str:
    """将秒数格式化为可读时长（用于 ETA 显示）。"""  # 好：说明用途
    if sec < 60:
        return f"{sec:.0f}s"
    elif sec < 3600:
        return f"{sec / 60:.0f}min"
    else:
        h = int(sec // 3600)
        m = int((sec % 3600) / 60)
        return f"{h}h{m}min"

# loader.py:35-53
def load_chapters_data(novel_dir: Path) -> list[dict]:
    """加载章节数据列表。

    优先级：
    1. chapters/ 目录下的分散 YAML 文件（章级分析默认输出格式）
    2. chapters.yaml 合并文件（旧格式或手动合并）

    同时从 chapter_index.yaml 读取 type 字段并合入返回数据。

    Args:
        novel_dir: 小说素材目录路径（如 NOVELS_DIR/material_id）

    Returns:
        章节数据列表，每项包含 chapter/title/type/summary/tension_level 等字段。
        加载失败时返回空列表。

    Raises:
        无。错误会被捕获并记录，返回空列表让调用方处理。
    """
```

**问题**：注释比代码还长，但没解释关键决策：
- 为什么"加载失败返回空列表"而不是抛异常？
- 为什么"优先分散文件"？
- `Raises: 无` 是什么意思？为什么不抛异常？

---

### 2.2 缺少关键注释

```python
# loader.py:27-32
_SAMPLE_THRESHOLD = 200  # 为什么是 200？
_AVG_TOKENS_PER_ENTRY = 40  # 为什么是 40？实测数据是什么？

# outline_core.py:133-148
system_prompt_premise = """你是专业的小说结构分析师。请根据提供的内容，生成以下 JSON：
{
  "premise": "一句话核心前提（50字以内）",
  ...
}"""
# 为什么 premise 限制 50 字？
# 为什么 total_acts 默认 3？
# 为什么 theme/tone 是数组？

# llm.py:24-28
_api_stats = {"calls": 0, "errors": 0, "tokens_total": 0}
_call_details: list[dict] = []
# 为什么用模块级变量而不是实例变量？
# 为什么 _call_details 限制 100 条？
```

**缺失的"为什么"注释**：
- 配置阈值的来源（实测数据、经验值、还是随便定的）
- 设计决策的原因（为什么这样而不是那样）
- 边界条件的处理策略（为什么返回空列表而不是抛异常）

---

### 2.3 过度注释

```python
# characters_core.py:143-188（核心人物处理）
# 每一步都有注释，但都是"做什么"
# 第一层：核心人物（>=50章）  ← 这行注释没用，代码已经表达了
new_core_count = 0
core_base_len = len(get_call_details())
if core_candidates:
    if progress_callback:
        progress_callback(0, total_batches, f"提取核心人物 ({len(core_candidates)} 人)")
    try:
        core_characters = _extract_character_batch(...)
    except Exception as e:
        logger.error(...)
        logger.warning(...)
        core_characters = []
        ...
```

**问题**：注释只是代码的中文翻译，没增加信息量。

---

## 三、公共模块复用问题

### 3.1 loader.py：复用但参数不一致

```python
# loader.py:225-279
def build_analysis_context(
    novel_dir: Path,
    config: dict,
    chapters_data: list | None = None,  # 可选参数
    material_id: str = "",              # 可选参数
    summary_tokens_key: str = "outline_summary_tokens",  # 默认值
    fallback_chars: int = 8000,         # 默认值
) -> tuple[str, str]:
```

**调用方使用不一致**：
```python
# outline_core.py:118
context_text = build_summary_pool(normal_chapters, config["llm"]["outline_summary_tokens"], model)
# 没用 build_analysis_context，直接调用 build_summary_pool

# worldbuilding.py（没看到）
# characters_core.py:111-117
context_text, context_label = build_analysis_context(
    novel_dir, config, chapters_data, material_id=material_id,
    summary_tokens_key="characters_summary_tokens",  # 不同参数
    fallback_chars=8000,  # 不同默认值
)
```

**问题**：
- 参数多、默认值多，调用方容易出错
- outline 直接调用 `build_summary_pool`，跳过了 `build_analysis_context`
- 不同模块用不同的 `summary_tokens_key`，没有统一约定

---

### 3.2 yaml.safe_load：124处重复调用

**分布**：
```
pipeline/：约 40处
storage/：约 20处
validation/：约 15处
cli/：约 10处
其他：约 39处
```

**问题**：
- 没有统一的 YAML 读写层
- 改编码（utf-8 → 其他）要改 124 处
- 改错误处理策略要改 124 处
- 每次都写 `with open(...) as f: yaml.safe_load(f)`，重复代码

**应该有**：
```python
# infra/yaml_io.py
def load_yaml(path: Path) -> dict:
    """统一的 YAML 读取，处理编码和错误"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        logger.error(f"YAML 解析错误: {path}: {e}")
        raise YAMLParseError(path, e)

def save_yaml(path: Path, data: dict) -> None:
    """统一的 YAML 写入"""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

---

### 3.3 常量分散定义

```python
# infra/common.py
KEY_PLOT_POINT_VALUES = [...]
NOVEL_TYPE_VALUES = [...]
TENSION_CHANGE_VALUES = [...]
HOOK_TYPE_VALUES = [...]

# 但有些常量还在其他地方：
# pipeline/analyze_utils.py
_SYSTEM_PROMPT = """..."""  # 应该在 prompts.py
_SAMPLE_THRESHOLD = 200     # 应该在 config.py
_AVG_TOKENS_PER_ENTRY = 40  # 应该在 config.py

# pipeline/characters_stats.py
CHARACTER_THRESHOLDS = {"core": 50, "supporting": 10, "minor": 5}
VALID_ROLES = ["protagonist", "antagonist", "supporting", "minor"]

# storage/sync_utils.py
DATABASE_URL = os.getenv("DATABASE_URL")  # 应该在 config.py
```

**问题**：
- 常量没有统一位置
- 改阈值要找多个文件
- 有些常量和配置混在一起

---

## 四、命名和风格问题

### 4.1 私有函数标记不一致

```python
# loader.py
def load_chapters_data(...)     # 公开，无下划线
def build_summary_pool(...)     # 公开，无下划线
def build_analysis_context(...) # 公开，无下划线
def _entry(ch: dict) -> str:    # 私有，有下划线（但只在 build_summary_pool 内用）

# analyze_utils.py
def _fmt_duration(...)          # 私有，有下划线
def _get_max_chapter_tokens()   # 私有，有下划线
def validate_chapter_analysis() # 公开，无下划线（但只在 analyze.py 内用）
def build_sliding_window_context()  # 公开，无下划线（但导出在 __all__）

# outline_temp.py
def _save_acts_temp(...)        # 私有，有下划线
def _load_acts_temp(...)        # 私有，有下划线
```

**问题**：
- 有些内部函数没下划线（如 `validate_chapter_analysis`）
- 有些导出的函数有下划线（如 `_SYSTEM_PROMPT` 在 `__all__`）
- 规则不一致：是"模块内私有"还是"包内私有"还是"公开"？

---

### 4.2 导出 logger 作为模块变量

```python
# sync_utils.py:108-116
__all__ = [
    "_load_embeddings_npz",
    "DatabaseConfigError",
    "QualityCheckError",
    "SchemaValidationError",
    "get_db_connection",
    "DATABASE_URL",
    "logger",  # ← 导出 logger
]
```

**问题**：
- logger 是单例，导出后所有导入方共享同一个
- 无法按场景定制 logger
- 测试时无法 mock

**应该**：
```python
# 不要导出 logger，让调用方自己获取
__all__ = [
    "get_db_connection",
    "DatabaseConfigError",
    ...
]

# 调用方
from novel_material.infra.progress import get_pipeline_logger
logger = get_pipeline_logger()
```

---

### 4.3 函数参数过多

```python
# analyze_utils.py:251-258
def build_sliding_window_context(
    chapter_num: int,
    chapters_data: dict[int, dict],
    lines: list[str],
    chapter_index: list[dict],
    evaluation: dict | None,
    next_preview_chars: int = 500,  # 6 个参数
) -> dict:

# llm.py:276-285
def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: dict,
    max_tokens_override: int | None = None,
    timeout_override: int | None = None,
    context: str | None = None,
    thinking_budget: int | None = None,
    temperature_override: float | None = None,  # 8 个参数
) -> dict:

# loader.py:225-232
def build_analysis_context(
    novel_dir: Path,
    config: dict,
    chapters_data: list | None = None,
    material_id: str = "",
    summary_tokens_key: str = "outline_summary_tokens",
    fallback_chars: int = 8000,  # 6 个参数
) -> tuple[str, str]:
```

**问题**：
- 参数超过 4 个就应该考虑用对象封装
- 可选参数多，调用方容易漏掉或顺序错误
- 默认值分散在函数签名里，难以统一管理

**应该**：
```python
class SlidingWindowContextArgs:
    chapter_num: int
    chapters_data: dict[int, dict]
    lines: list[str]
    chapter_index: list[dict]
    evaluation: dict | None
    next_preview_chars: int = 500

def build_sliding_window_context(args: SlidingWindowContextArgs) -> dict:
```

---

## 五、真正的架构问题

### 5.1 配置分散

```python
# infra/config.py
def get_settings() -> dict:  # 从 settings.yaml 读配置

# infra/llm.py
def load_config(provider) -> dict:  # 从 providers.yaml 读配置，合并 settings.yaml

# 各模块直接调用
config = load_config(provider)  # pipeline 模块
settings = get_settings()       # analyze_utils 模块
```

**问题**：
- 两个配置入口，不知道用哪个
- load_config 内部合并逻辑复杂（第67-155行）
- 配置结构不透明（返回 dict，没有类型）

---

### 5.2 模块级初始化

```python
# infra/llm.py:24-28
_api_stats = {"calls": 0, "errors": 0, "tokens_total": 0}
_call_details: list[dict] = []

# storage/sync_utils.py:16
DATABASE_URL = os.getenv("DATABASE_URL")

# 各模块
logger = get_pipeline_logger()  # 模块级初始化
```

**问题**：
- 模块级变量在 import 时就初始化
- 无法延迟初始化（比如测试环境不需要 DATABASE_URL）
- 无法多实例（比如同时处理多个 material_id）

---

### 5.3 缺少抽象层

**当前架构**：
```
CLI → 直接调用函数 → 直接操作文件/LLM/数据库
```

**应该有**：
```
CLI → Application Service → Domain Logic → Infrastructure Service
       ↓                    ↓              ↓
    组合调用            纯业务逻辑       纯 IO 操作
```

**缺失的服务层**：
- `NovelStorage`：统一所有文件操作（yaml 读写、路径拼接）
- `LLMService`：统一所有 LLM 调用（配置加载、统计）
- `ValidationService`：统一所有校验（模型校验 + 数据加载）

---

## 六、总结：重构文档遗漏的核心问题

| 问题 | 重构文档提到 | 实际严重程度 |
|------|-------------|-------------|
| 日志耦合（24个文件） | 未提到 | 高 |
| 路径耦合（20个文件） | 未提到 | 高 |
| YAML 读写分散（124处） | 未提到 | 高 |
| 模块边界模糊 | 未提到 | 高 |
| 注释冗余/缺失 | 未提到 | 中 |
| 常量分散定义 | 部分解决 | 中 |
| 函数参数过多 | 未提到 | 中 |
| 配置入口分散 | 未提到 | 高 |
| 模块级初始化 | 未提到 | 高 |
| 缺少服务层抽象 | 未提到 | 高 |

**一句话总结**：
> 重构文档做了"表面整理"，但没触及"内部腐烂"。代码的真正问题不是"导入路径乱"，而是"职责不清、边界模糊、基础设施渗透到业务逻辑"。

---

## 七、建议的真正重构方向

### 优先级1：建立服务层

```python
# infra/services.py
class Services:
    """所有基础设施服务的统一入口"""

    def __init__(self, config_path: Path):
        self.storage = NovelStorage(config_path)
        self.llm = LLMService()
        self.validation = ValidationService()

# 所有模块通过 Services 获取服务，而不是直接导入
```

### 优先级2：统一 IO 层

```python
# infra/yaml_io.py
def load_yaml(path: Path) -> dict: ...
def save_yaml(path: Path, data: dict) -> None: ...

# infra/path_service.py
class PathService:
    def novel_dir(self, material_id: str) -> Path: ...
    def meta_path(self, material_id: str) -> Path: ...
    def chapters_path(self, material_id: str) -> Path: ...
```

### 优先级3：拆分大模块

按职责拆分，不是按行数拆分：
- `analyze_utils.py` → `prompts.py` + `validators.py` + `file_ops.py`
- `outline_core.py` → 业务逻辑 + 存储逻辑（分离）
- `validation/schema.py` → `models.py` + `validators.py` + `loader.py`

### 优先级4：补注释，删冗余

- 删除"做什么"注释（代码已经表达了）
- 补充"为什么"注释（设计决策、阈值来源）
- 关键边界条件说明（为什么返回空列表而不是抛异常）