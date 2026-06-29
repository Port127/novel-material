"""校验函数：输入数据，返回错误列表。

此模块包含所有校验函数，用于验证 YAML 文件数据是否符合模型约束。
校验函数返回错误描述列表，空列表表示校验通过。
"""
import sys
from typing import Optional

from pydantic import ValidationError as PydanticValidationError

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml, load_yaml_list
from novel_material.infra.logging_config import get_pipeline_logger
from novel_material.tags.validate import validate_tag, validate_tags_batch
from novel_material.infra.common import HOOK_TYPE_VALUES
from novel_material.validation.models import (
    MetaModel,
    ChapterEntryModel,
    EvaluationModel,
    NovelTagsModel,
)

__all__ = [
    "validate_meta",
    "validate_chapters",
    "get_schema_error_chapters",
    "validate_novel_tags",
    "validate_chapter_tags_fields",
    "validate_chapter_tags",
    "validate_evaluation",
    "validate_material",
]

logger = get_pipeline_logger()


def validate_meta(material_id: str) -> list[str]:
    """校验 meta.yaml，返回错误描述列表（空列表 = 通过）。"""
    meta_file = NOVELS_DIR / material_id / "meta.yaml"
    if not meta_file.exists():
        return [f"meta.yaml 不存在：{meta_file}"]

    data = load_yaml(meta_file)

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

    chapters = load_yaml_list(chapters_file)

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


def get_schema_error_chapters(material_id: str, start_ch: int | None = None, end_ch: int | None = None) -> list[int]:
    """获取 schema 校验失败的章节号列表。

    复用 validate_chapters 的返回值，提取错误信息中的章节号。

    参数：
        material_id：素材 ID
        start_ch：起始章节号（可选）
        end_ch：结束章节号（可选）

    返回：
        校验失败的章节号列表（按章节号排序，去重）
    """
    errors = validate_chapters(material_id, start_ch=start_ch, end_ch=end_ch)
    if not errors:
        return []

    # 从 "第441章 [field]: msg" 提取章节号
    chapters: set[int] = set()
    for err in errors:
        if err.startswith("第") and "章" in err:
            try:
                ch_str = err.split("第")[1].split("章")[0]
                chapters.add(int(ch_str))
            except (ValueError, IndexError):
                continue

    return sorted(chapters)


def validate_novel_tags(material_id: str) -> list[str]:
    """校验 tags.yaml（小说级），返回错误描述列表。"""
    tags_file = NOVELS_DIR / material_id / "tags.yaml"
    if not tags_file.exists():
        return []

    data = load_yaml(tags_file)

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

    注意：
        emotional_tone/scene_type/technique 不做白名单校验，允许 LLM 自由发挥，
        以后再整理字典。只校验类型（必须是数组）。
    """
    errors = []

    # hook_type 校验（白名单）
    hook_type = result.get("hook_type")
    if hook_type:
        if hook_type not in HOOK_TYPE_VALUES:
            errors.append(f"hook_type 值 '{hook_type}' 不合法，合法值：{HOOK_TYPE_VALUES}")

    # emotional_tone 校验（仅类型）
    emotional_tone = result.get("emotional_tone")
    if emotional_tone:
        if not isinstance(emotional_tone, list):
            errors.append(f"emotional_tone 应为数组，实际类型：{type(emotional_tone).__name__}")

    # scene_type 校验（仅类型）
    scene_type = result.get("scene_type")
    if scene_type:
        if not isinstance(scene_type, list):
            errors.append(f"scene_type 应为数组，实际类型：{type(scene_type).__name__}")

    # technique 校验（仅类型）
    technique = result.get("technique")
    if technique:
        if not isinstance(technique, list):
            errors.append(f"technique 应为数组，实际类型：{type(technique).__name__}")

    return errors


def validate_chapter_tags(material_id: str, start_ch: int | None = None, end_ch: int | None = None) -> list[str]:
    """校验 chapters.yaml 中的章节级标签字段。

    参数：
        material_id: 素材 ID
        start_ch: 起始章节号（可选）
        end_ch: 结束章节号（可选）

    校验字段：
        - chapter_functions（白名单校验）
        - hook_type（白名单校验）
        - emotional_tone/scene_type/technique（仅类型校验，不做白名单限制）
    """
    chapters_file = NOVELS_DIR / material_id / "chapters.yaml"
    if not chapters_file.exists():
        return []

    chapters = load_yaml_list(chapters_file)

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
    eval_file = NOVELS_DIR / material_id / "evaluation.yaml"
    if not eval_file.exists():
        return []  # 可选文件，不存在不报错

    data = load_yaml(eval_file)

    errors: list[str] = []
    try:
        EvaluationModel(**data)
    except PydanticValidationError as exc:
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            errors.append(f"evaluation.yaml [{field}]: {err['msg']}")

    return errors


# 综合入口

def validate_material(
    material_id: str,
    verbose: bool = True,
    start_ch: int | None = None,
    end_ch: int | None = None,
    skip_tags: bool = False,
) -> bool:
    """对指定素材运行所有校验，返回 True 表示全部通过。

    参数：
        material_id: 素材 ID
        verbose: 是否输出详细信息
        start_ch: 起始章节号（可选，仅校验指定范围）
        end_ch: 结束章节号（可选）
        skip_tags: 跳过标签字典校验（用于同步场景，标签不在字典不影响数据完整性）
    """
    all_errors: list[str] = []

    # 核心结构校验（必须通过）
    core_checks = [
        ("meta.yaml 结构校验", lambda m: validate_meta(m)),
        ("chapters.yaml 结构校验", lambda m: validate_chapters(m, start_ch=start_ch, end_ch=end_ch)),
    ]

    # 标签字典校验（可选跳过）
    tag_checks = [
        ("小说级标签校验", validate_novel_tags),
        ("章节标签字段校验", lambda m: validate_chapter_tags(m, start_ch=start_ch, end_ch=end_ch)),
    ]

    # 可选文件校验
    optional_checks = [
        ("总体评估校验", validate_evaluation),
    ]

    checks = core_checks + ([] if skip_tags else tag_checks) + optional_checks

    for label, fn in checks:
        errs = fn(material_id)
        if verbose:
            if errs:
                print(f"  ✗ {label}：{len(errs)} 个错误")
                for e in errs[:5]:  # 只显示前 5 个错误
                    print(f"      {e}")
                if len(errs) > 5:
                    print(f"      ... 共 {len(errs)} 个错误")
            else:
                print(f"  ✓ {label}")
        all_errors.extend(errs)

    passed = len(all_errors) == 0
    if verbose:
        if skip_tags:
            print(f"\nSchema 校验（已跳过标签校验）：{material_id} {'通过' if passed else '失败'}")
        else:
            print(f"\nSchema 校验{'通过' if passed else '失败'}：{material_id}")

    return passed


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python validators.py <material_id>")
        sys.exit(1)

    ok = validate_material(sys.argv[1])
    sys.exit(0 if ok else 1)
