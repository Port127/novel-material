"""Schema 结构校验器：基于 pydantic 对核心 YAML 文件做结构验证。"""
import re
import sys
import yaml
from pathlib import Path
from typing import Optional, Any

from pydantic import BaseModel, field_validator, Field
from pydantic import ValidationError as PydanticValidationError

from novel_material.infra.config import NOVELS_DIR, VALID_STATUSES, TAGS_VIEW_FILE
from novel_material.infra.logging_config import get_pipeline_logger
from novel_material.tags.validate import validate_tag, validate_tags_batch
from novel_material.validation.pacing_normalize import PACING_CORE, normalize_pacing
from novel_material.infra.constants import KEY_PLOT_POINT_VALUES, TENSION_CHANGE_VALUES, HOOK_TYPE_VALUES

# 常量
_MATERIAL_ID_PATTERN = re.compile(r"^nm_[a-z]+_\d{8}_[a-z0-9]{4}$")
_VALID_STATUSES = set(VALID_STATUSES)
_VALID_PACING = PACING_CORE  # 使用核心集合，变体已在前置规范化处理

logger = get_pipeline_logger()

# ── 章节级标签白名单（从 tags_view.yaml 加载）──
# 设计说明：tags 表用于小说级标签（element/setting/style/structure），
# 章节级标签（情感基调/场景类型/叙事技巧）在 tags_view.yaml 中单独分组，两者用途不同。
_CHAPTER_TAG_WHITELIST: dict[str, set[str]] = {}


def _load_chapter_tag_whitelist() -> dict[str, set[str]]:
    """加载章节级标签白名单（情感基调/场景类型/叙事技巧）。

    返回：
        dict：{分组名: 标签集合}
    """
    if _CHAPTER_TAG_WHITELIST:
        return _CHAPTER_TAG_WHITELIST

    if not TAGS_VIEW_FILE.exists():
        logger.warning(f"tags_view.yaml 不存在：{TAGS_VIEW_FILE}")
        return {}

    with open(TAGS_VIEW_FILE, "r", encoding="utf-8") as f:
        tags_view = yaml.safe_load(f) or {}

    chapter_func = tags_view.get("chapter_function", {})
    common = chapter_func.get("common", {})

    # 提取三个分组
    for group_name in ("情感基调", "场景类型", "叙事技巧"):
        tags_list = common.get(group_name, [])
        if isinstance(tags_list, list):
            _CHAPTER_TAG_WHITELIST[group_name] = set(tags_list)

    return _CHAPTER_TAG_WHITELIST


# Pydantic 模型

class MetaModel(BaseModel):
    """meta.yaml 的最小必填字段约束。"""
    material_id: str
    name: str
    status: str
    word_count: Optional[int] = None
    chapter_count: Optional[int] = None

    @field_validator("material_id")
    @classmethod
    def check_material_id(cls, v: str) -> str:
        if not _MATERIAL_ID_PATTERN.match(v):
            raise ValueError(
                f"material_id 格式不符（期望 nm_{{type}}_YYYYMMDD_{{4位字母数字}}），实际：{v}"
            )
        return v

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name 不能为空")
        return v

    @field_validator("status")
    @classmethod
    def check_status(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(
                f"status 值 '{v}' 不合法，合法值：{sorted(_VALID_STATUSES)}"
            )
        return v

    @field_validator("word_count", "chapter_count", mode="before")
    @classmethod
    def check_positive_int(cls, v: Any) -> Optional[int]:
        if v is None:
            return None
        if not isinstance(v, int) or v <= 0:
            raise ValueError(f"必须为正整数，实际：{v!r}")
        return v


class ChapterEntryModel(BaseModel):
    """chapters.yaml 单章条目的字段约束。"""
    chapter: int = Field(..., ge=1)
    title: str
    summary: str = Field(..., min_length=40, max_length=500)  # 与 quality.py 阈值统一
    tension_level: int = Field(..., ge=1, le=5)
    characters_appear: list = Field(default_factory=list)
    chapter_functions: Optional[list] = None
    pacing: Optional[str] = None
    key_plot_point: Optional[str] = None  # 结构角色标记（代码推断）
    key_event: Optional[str] = Field(None, max_length=100)  # 关键事件描述（LLM生成）
    # 滑动窗口新增字段（阶段二）
    tension_change: Optional[str] = None  # 张力变化方向（上升/持平/下降）
    emotion_transition: Optional[str] = Field(None, max_length=100)  # 情感过渡描述（10-50字）
    plot_progress: Optional[str] = Field(None, max_length=200)  # 情节进度描述（20-100字）
    # 章节级标签（阶段四新增）
    emotional_tone: Optional[list[str]] = None  # 情感基调（从标签字典选取）
    scene_type: Optional[list[str]] = None  # 场景类型（从标签字典选取）
    technique: Optional[list[str]] = None  # 叙事技巧（从标签字典选取）
    hook_type: Optional[str] = None  # 章末钩子类型

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title 不能为空")
        return v

    @field_validator("pacing")
    @classmethod
    def check_pacing(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        # 先规范化再校验（兼容 LLM 输出变体）
        normalized = normalize_pacing(v)
        if normalized not in _VALID_PACING:
            raise ValueError(
                f"pacing 值 '{v}' 规范化后 '{normalized}' 仍不合法，合法值：{_VALID_PACING}"
            )
        return normalized  # 返回规范化后的值

    @field_validator("key_plot_point")
    @classmethod
    def check_key_plot_point(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in KEY_PLOT_POINT_VALUES:
            raise ValueError(
                f"key_plot_point 值 '{v}' 不合法，合法值：{KEY_PLOT_POINT_VALUES}"
            )
        return v

    @field_validator("tension_change")
    @classmethod
    def check_tension_change(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in TENSION_CHANGE_VALUES:
            raise ValueError(
                f"tension_change 值 '{v}' 不合法，合法值：{TENSION_CHANGE_VALUES}"
            )
        return v

    @field_validator("hook_type")
    @classmethod
    def check_hook_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if v not in HOOK_TYPE_VALUES:
            raise ValueError(
                f"hook_type 值 '{v}' 不合法，合法值：{HOOK_TYPE_VALUES}"
            )
        return v


class EvaluationModel(BaseModel):
    """evaluation.yaml 的字段约束。"""
    schema_version: str = Field(..., pattern=r"^2\.0\.1$")
    novel_type: list[str] = Field(..., min_length=1, max_length=3)
    main_thread_summary: str = Field(..., min_length=100, max_length=500)  # ROADMAP: 200-300字，放宽边界
    total_chapters: int = Field(..., ge=1)
    core_characters_hint: list[str] = Field(..., min_length=3, max_length=10)
    stage_summaries: dict[int, str] = Field(...)

    @field_validator("novel_type")
    @classmethod
    def check_novel_type(cls, v: list[str]) -> list[str]:
        # 放宽校验：只检查是否为非空字符串，不强制白名单
        # 原因：LLM 可能返回不在字典中的类型，允许后续人工审核
        for t in v:
            if not t or not t.strip():
                raise ValueError(f"novel_type 包含空值")
        return v

    @field_validator("stage_summaries")
    @classmethod
    def check_stage_summaries(cls, v: dict[int, str]) -> dict[int, str]:
        required_stages = {1, 2, 3, 4, 5}
        if set(v.keys()) != required_stages:
            raise ValueError(f"stage_summaries 必须包含5个阶段（1-5），实际：{sorted(v.keys())}")
        return v


class NovelTagsModel(BaseModel):
    """tags.yaml（小说级标签）的最小字段约束。"""
    material_id: str
    channel: Optional[str] = None
    genre_primary: Optional[list[str]] = None  # 支持多主题材
    genre_secondary: Optional[Any] = None
    elements: Optional[Any] = None
    style: Optional[Any] = None
    structure: Optional[str] = None
    setting: Optional[str] = None
    hooks: Optional[Any] = None
    tropes: Optional[Any] = None
    themes: Optional[Any] = None
    # 兼容旧字段
    genre: Optional[Any] = None
    theme: Optional[Any] = None
    tone: Optional[Any] = None

    @field_validator("material_id")
    @classmethod
    def check_material_id(cls, v: str) -> str:
        if not _MATERIAL_ID_PATTERN.match(v):
            raise ValueError(f"material_id 格式不符，实际：{v}")
        return v


# 校验函数

def validate_meta(material_id: str) -> list[str]:
    """校验 meta.yaml，返回错误描述列表（空列表 = 通过）。"""
    meta_file = NOVELS_DIR / material_id / "meta.yaml"
    if not meta_file.exists():
        return [f"meta.yaml 不存在：{meta_file}"]

    with open(meta_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    errors: list[str] = []
    try:
        MetaModel(**{k: data.get(k) for k in MetaModel.model_fields})
    except PydanticValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            errors.append(f"meta.yaml [{field}]: {err['msg']}")

    return errors


def validate_chapters(material_id: str, start_ch: int | None = None, end_ch: int | None = None) -> list[str]:
    """校验 chapters.yaml 所有条目，返回错误描述列表。

    参数：
        material_id: 素材 ID
        start_ch: 起始章节号（可选，仅校验指定范围）
        end_ch: 结束章节号（可选）
    """
    chapters_file = NOVELS_DIR / material_id / "chapters.yaml"
    if not chapters_file.exists():
        return [f"chapters.yaml 不存在：{chapters_file}"]

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        return ["chapters.yaml 为空，无章节数据"]

    errors: list[str] = []
    for entry in chapters:
        if not isinstance(entry, dict):
            errors.append("chapters.yaml 包含非字典条目")
            continue

        ch_num = entry.get("chapter", "?")

        # 范围过滤：只校验指定范围内的章节
        if start_ch is not None and isinstance(ch_num, int) and ch_num < start_ch:
            continue
        if end_ch is not None and isinstance(ch_num, int) and ch_num > end_ch:
            continue

        try:
            ChapterEntryModel(
                chapter=entry.get("chapter"),
                title=entry.get("title", ""),
                summary=entry.get("summary", ""),
                tension_level=entry.get("tension_level"),
                characters_appear=entry.get("characters_appear", []),
                chapter_functions=entry.get("chapter_functions", entry.get("chapter_function")),
                pacing=entry.get("pacing"),
                key_plot_point=entry.get("key_plot_point"),
                key_event=entry.get("key_event"),
                # 滑动窗口新增字段
                tension_change=entry.get("tension_change"),
                emotion_transition=entry.get("emotion_transition"),
                plot_progress=entry.get("plot_progress"),
                # 章节级标签（阶段四新增）
                emotional_tone=entry.get("emotional_tone"),
                scene_type=entry.get("scene_type"),
                technique=entry.get("technique"),
                hook_type=entry.get("hook_type"),
            )
        except PydanticValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(loc) for loc in err["loc"])
                errors.append(f"第{ch_num}章 [{field}]: {err['msg']}")

    return errors


def validate_novel_tags(material_id: str) -> list[str]:
    """校验 tags.yaml（小说级），返回错误描述列表。"""
    tags_file = NOVELS_DIR / material_id / "tags.yaml"
    if not tags_file.exists():
        return []

    with open(tags_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    errors: list[str] = []

    try:
        NovelTagsModel(
            material_id=data.get("material_id", ""),
            channel=data.get("channel"),
            genre_primary=data.get("genre_primary"),
            genre_secondary=data.get("genre_secondary"),
            elements=data.get("elements"),
            style=data.get("style"),
            structure=data.get("structure"),
            setting=data.get("setting"),
            genre=data.get("genre"),
            theme=data.get("theme"),
            tone=data.get("tone"),
        )
    except PydanticValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            errors.append(f"tags.yaml [{field}]: {err['msg']}")

    # 标签白名单校验
    elements = data.get("elements") or []
    if isinstance(elements, list):
        valid, invalid = validate_tags_batch("element", elements)
        for tag in invalid:
            errors.append(f"tags.yaml [elements]: '{tag}' 不在标签字典中")

    style_val = data.get("style")
    style_list = style_val if isinstance(style_val, list) else ([style_val] if style_val else [])
    if style_list:
        valid, invalid = validate_tags_batch("style", style_list)
        for tag in invalid:
            errors.append(f"tags.yaml [style]: '{tag}' 不在标签字典中")

    structure = data.get("structure")
    if structure:
        canonical = validate_tag("structure", structure)
        if not canonical:
            errors.append(f"tags.yaml [structure]: '{structure}' 不在标签字典中")

    setting = data.get("setting")
    if setting:
        canonical = validate_tag("setting", setting)
        if not canonical:
            errors.append(f"tags.yaml [setting]: '{setting}' 不在标签字典中")

    return errors


def validate_chapter_tags_fields(result: dict) -> list[str]:
    """校验章节级标签字段（阶段四新增），返回错误列表。

    参数：
        result：LLM 返回结果

    返回：
        list[str]：错误描述列表
    """
    errors = []

    # hook_type 校验（白名单）
    hook_type = result.get("hook_type")
    if hook_type:
        if hook_type not in HOOK_TYPE_VALUES:
            errors.append(f"hook_type 值 '{hook_type}' 不合法，合法值：{HOOK_TYPE_VALUES}")

    # 加载白名单
    whitelist = _load_chapter_tag_whitelist()

    # emotional_tone 校验（白名单 + 类型）
    emotional_tone = result.get("emotional_tone")
    if emotional_tone:
        if not isinstance(emotional_tone, list):
            errors.append(f"emotional_tone 应为数组，实际类型：{type(emotional_tone).__name__}")
        else:
            allowed = whitelist.get("情感基调", set())
            for tag in emotional_tone:
                if tag not in allowed:
                    errors.append(f"emotional_tone '{tag}' 不在字典中（建议审核入库）")

    # scene_type 校验（白名单 + 类型）
    scene_type = result.get("scene_type")
    if scene_type:
        if not isinstance(scene_type, list):
            errors.append(f"scene_type 应为数组，实际类型：{type(scene_type).__name__}")
        else:
            allowed = whitelist.get("场景类型", set())
            for tag in scene_type:
                if tag not in allowed:
                    errors.append(f"scene_type '{tag}' 不在字典中（建议审核入库）")

    # technique 校验（白名单 + 类型）
    technique = result.get("technique")
    if technique:
        if not isinstance(technique, list):
            errors.append(f"technique 应为数组，实际类型：{type(technique).__name__}")
        else:
            allowed = whitelist.get("叙事技巧", set())
            for tag in technique:
                if tag not in allowed:
                    errors.append(f"technique '{tag}' 不在字典中（建议审核入库）")

    return errors


def validate_chapter_tags(material_id: str, start_ch: int | None = None, end_ch: int | None = None) -> list[str]:
    """校验 chapters.yaml 中的章节级标签字段。

    参数：
        material_id: 素材 ID
        start_ch: 起始章节号（可选）
        end_ch: 结束章节号（可选）

    校验字段：
        - chapter_functions（硬性白名单）
        - hook_type（硬性白名单）
        - emotional_tone/scene_type/technique（开放字典，建议入库）
    """
    chapters_file = NOVELS_DIR / material_id / "chapters.yaml"
    if not chapters_file.exists():
        return []

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    errors: list[str] = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch_num = ch.get("chapter", "?")

        # 范围过滤
        if start_ch is not None and isinstance(ch_num, int) and ch_num < start_ch:
            continue
        if end_ch is not None and isinstance(ch_num, int) and ch_num > end_ch:
            continue

        funcs = ch.get("chapter_functions", ch.get("chapter_function", []))
        if isinstance(funcs, list) and funcs:
            valid, invalid = validate_tags_batch("chapter_function", funcs)
            for tag in invalid:
                errors.append(f"第{ch_num}章: chapter_functions '{tag}' 不在字典中")

        # D5 新增：校验章节级标签字段
        tags_errors = validate_chapter_tags_fields(ch)
        for err in tags_errors:
            errors.append(f"第{ch_num}章: {err}")

    return errors


def validate_evaluation(material_id: str) -> list[str]:
    """校验 evaluation.yaml（可选文件），返回错误描述列表。"""
    eval_file = NOVELS_DIR / material_id / "meta" / "evaluation.yaml"
    if not eval_file.exists():
        return []  # 可选文件，不存在不报错

    with open(eval_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    errors: list[str] = []
    try:
        EvaluationModel(
            schema_version=data.get("schema_version", ""),
            novel_type=data.get("novel_type", []),
            main_thread_summary=data.get("main_thread_summary", ""),
            total_chapters=data.get("total_chapters", 0),
            core_characters_hint=data.get("core_characters_hint", []),
            stage_summaries=data.get("stage_summaries", {}),
        )
    except PydanticValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            errors.append(f"evaluation.yaml [{field}]: {err['msg']}")

    return errors


# 综合入口

def validate_material(material_id: str, verbose: bool = True, start_ch: int | None = None, end_ch: int | None = None) -> bool:
    """对指定素材运行所有校验，返回 True 表示全部通过。

    参数：
        material_id: 素材 ID
        verbose: 是否输出详细信息
        start_ch: 起始章节号（可选，仅校验指定范围）
        end_ch: 结束章节号（可选）
    """
    all_errors: list[str] = []

    # meta/tags 校验不受范围限制，章节校验应用范围过滤
    checks = [
        ("meta.yaml 结构校验", lambda m: validate_meta(m)),
        ("chapters.yaml 结构校验", lambda m: validate_chapters(m, start_ch=start_ch, end_ch=end_ch)),
        ("小说级标签校验", validate_novel_tags),
        ("总体评估校验", validate_evaluation),  # 可选文件校验
        ("章节功能标签字典校验", lambda m: validate_chapter_tags(m, start_ch=start_ch, end_ch=end_ch)),
    ]

    for label, fn in checks:
        errs = fn(material_id)
        if verbose:
            if errs:
                print(f"  ✗ {label}：{len(errs)} 个错误")
                for e in errs:
                    print(f"      {e}")
            else:
                print(f"  ✓ {label}")
        all_errors.extend(errs)

    passed = len(all_errors) == 0
    if verbose:
        if passed:
            print(f"\nSchema 校验通过：{material_id}")
        else:
            print(f"\nSchema 校验失败：{len(all_errors)} 个错误 [{material_id}]")

    return passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python schema.py <material_id>")
        sys.exit(1)

    ok = validate_material(sys.argv[1])
    sys.exit(0 if ok else 1)