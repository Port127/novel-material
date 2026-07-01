"""章节分析校验函数：纯逻辑校验，无 IO 操作。

此模块包含 analyze 流水线所需的所有校验函数，
用于验证 LLM 返回的章节分析结果是否符合预期格式和约束。
"""
from novel_material.infra.common import TENSION_CHANGE_VALUES
from novel_material.infra.llm_contracts import (
    LLMResponseContractError,
    require_integer,
    require_mapping,
    require_string,
    require_string_list,
)


def normalize_chapter_analysis_response(payload: object) -> dict:
    """校验单章分析响应的基础字段类型。"""
    result = dict(require_mapping(payload, "chapter_analysis"))
    for field in ("summary", "key_event", "hook_type"):
        result[field] = require_string(result.get(field), f"chapter_analysis.{field}")
    for field in (
        "characters_appear",
        "chapter_functions",
        "setting",
        "emotional_tone",
        "scene_type",
        "technique",
    ):
        result[field] = require_string_list(
            result.get(field), f"chapter_analysis.{field}"
        )
    tension = require_integer(
        result.get("tension_level"), "chapter_analysis.tension_level"
    )
    if not 1 <= tension <= 5:
        raise LLMResponseContractError(
            "chapter_analysis.tension_level", "1-5 的整数", tension
        )
    result["tension_level"] = tension
    result["pacing"], quality = _recover_pacing(result)
    if quality is not None:
        existing_quality = result.get("quality")
        if not isinstance(existing_quality, dict):
            existing_quality = {}
        result["quality"] = {**existing_quality, **quality}
    for field in ("tension_change", "emotion_transition", "plot_progress"):
        if result.get(field) is not None:
            result[field] = require_string(result[field], f"chapter_analysis.{field}")
    return result


def _recover_pacing(payload: dict) -> tuple[str, dict | None]:
    value = payload.get("pacing")
    if value is not None:
        return require_string(value, "chapter_analysis.pacing"), None

    tension = payload.get("tension_level")
    functions = [str(item) for item in payload.get("chapter_functions", []) or []]
    joined = " ".join(functions)
    if tension in (4, 5) or any(
        keyword in joined for keyword in ("战斗", "冲突", "追逃", "危机")
    ):
        pacing = "快"
    elif tension in (1, 2) or any(
        keyword in joined for keyword in ("日常", "过渡", "铺垫", "休整")
    ):
        pacing = "慢"
    else:
        pacing = "中"
    return pacing, {
        "fallback_fields": ["pacing"],
        "fallback_reason": {
            "pacing": "LLM 返回 null，按 tension_level/chapter_functions 推断",
        },
    }


def validate_window_fields(result: dict, prev_tension: int | None) -> list[str]:
    """校验滑动窗口新增字段，返回错误列表。

    参数：
        result：LLM 返回结果
        prev_tension：前章张力值（用于校验 tension_change）

    返回：
        list[str]：错误描述列表
    """
    errors = []

    # tension_change 校验
    tension_change = result.get("tension_change")
    if tension_change:
        if tension_change not in TENSION_CHANGE_VALUES:
            errors.append(f"tension_change 值 '{tension_change}' 不合法")

        # 检查与前章张力的一致性（如果有）
        if prev_tension is not None:
            current_tension = result.get("tension_level", 0)
            if current_tension:
                expected_change = None
                if current_tension > prev_tension:
                    expected_change = "上升"
                elif current_tension < prev_tension:
                    expected_change = "下降"
                else:
                    expected_change = "持平"

                if tension_change != expected_change:
                    errors.append(
                        f"tension_change '{tension_change}' 与张力变化不一致 "
                        f"(前章{prev_tension}→当前{current_tension}，期望'{expected_change}')"
                    )

    # emotion_transition 校验
    emotion = result.get("emotion_transition")
    if emotion and len(emotion) < 5:
        errors.append(f"emotion_transition 过短 ({len(emotion)}字)")

    # plot_progress 校验
    progress = result.get("plot_progress")
    if progress and len(progress) < 10:
        errors.append(f"plot_progress 过短 ({len(progress)}字)")

    return errors


def _validate_chapter_analysis(result: dict, chapter_info: dict) -> list[str]:
    """检查分析结果是否合格，返回问题列表。

    检查项：
    - 摘要长度是否足够
    - tension_level 是否在有效范围内
    - 是否识别到出场人物

    特殊类型章节（afterword/author_note）放宽检查。
    """
    errors = []
    ch_num = chapter_info.get("chapter", "?")
    ch_type = chapter_info.get("type", "normal")

    # 特殊类型：放宽检查
    if ch_type in ("afterword", "author_note"):
        summary = result.get("summary", "")
        if len(summary) < 20:  # 降低阈值
            errors.append(f"章节{ch_num}: 摘要过短({len(summary)}字)")
        # 不检查人物和张力
        return errors

    # 正文/番外：完整检查

    summary = result.get("summary", "")
    if len(summary) < 40:
        errors.append(f"章节{ch_num}: 摘要过短({len(summary)}字)")

    tension = result.get("tension_level")
    if tension is not None and not (1 <= tension <= 5):
        errors.append(f"章节{ch_num}: tension_level 不在 1-5 范围")

    if not result.get("characters_appear"):
        errors.append(f"章节{ch_num}: 未识别到出场人物")

    return errors


__all__ = [
    "normalize_chapter_analysis_response",
    "validate_window_fields",
]
