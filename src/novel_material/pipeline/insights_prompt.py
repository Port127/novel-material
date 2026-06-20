"""Prompt construction for chapter insight analysis."""

from __future__ import annotations

import json

from novel_material.analysis_profiles import AnalysisProfile

COMMON_FIELD_NAMES = {
    "core_event",
    "scene_goal",
    "conflict",
    "stakes",
    "turning_point",
    "reader_hook",
    "character_change",
    "writing_takeaway",
}


def build_insight_schema_text(profile: AnalysisProfile) -> str:
    """Build a JSON schema example from merged profile fields."""
    common_fields = {
        name: f"{field.description}，{field.min_length or 1}-{field.max_length or 200}字"
        for name, field in profile.required_fields.items()
        if name in COMMON_FIELD_NAMES
    }
    genre_fields = {
        name: f"{field.description}，{field.min_length or 1}-{field.max_length or 200}字"
        for name, field in profile.required_fields.items()
        if name not in COMMON_FIELD_NAMES
    }
    optional_fields = {
        name: field.description
        for name, field in profile.optional_fields.items()
    }
    example = {
        "schema_version": "1.0",
        "common": common_fields,
        "genre": genre_fields,
        "optional": optional_fields,
        "evidence": [{"field": "core_event", "source": "chapter_summary", "text": "依据文本"}],
        "confidence": 0.8,
        "quality": {"repaired": False, "validation_errors": []},
    }
    return json.dumps(example, ensure_ascii=False, indent=2)


def build_insight_system_prompt(profile: AnalysisProfile) -> str:
    """Build the system prompt for chapter insight analysis."""
    additions = "\n".join(f"- {item}" for item in profile.prompt_additions)
    return f"""你是专业的小说创作机制分析师，但必须按中等模型可稳定完成的方式工作。

你的任务不是复述剧情，而是分析这一章为什么有效、如何服务读者期待、如何为创作提供可复用经验。

当前分析 profile: {profile.display_name}

分析要求：
- 只输出 JSON，不要输出 Markdown、解释文字或推理过程。
- 事实必须来自章节摘要、章级分析字段或原文片段。
- 先给具体事件，再解释叙事功能。
- writing_takeaway 必须是可执行的写作建议。
- 每个必填字段尽量对应 1 条 evidence；evidence.text 控制在 120 字以内。
- 如果信息不足，不要编造；必填字段写“无明显推进”，optional 字段可以省略。
- confidence 表示本次分析可信度，范围 0.0-1.0。
- 不要使用“剧情精彩”“人物饱满”“节奏紧凑”这类泛化评价。

profile 额外要求：
{additions}
"""


def build_repair_prompt(errors: list[str], previous_result: dict) -> str:
    """Build a constrained repair prompt for invalid insight JSON."""
    return f"""上一次 JSON 没有通过校验。

只修复这些错误，不要增加无依据内容：
{json.dumps(errors, ensure_ascii=False, indent=2)}

上一次结果：
{json.dumps(previous_result, ensure_ascii=False, indent=2)}

请只输出修复后的 JSON。
"""
