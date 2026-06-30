"""作品画像生成的提示词构造器。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def build_work_profile_prompt(context: dict) -> tuple[str, str]:
    """返回 work_profile 生成所需的 system 和 user prompt。"""
    system_prompt = "\n".join(
        (
            "你是小说素材分析助手，负责生成面向写作 Agent 的 work_profile.yaml。",
            "work_profile.yaml 不是事实来源，只能作为作品级导航、创作策略和检索入口。",
            "不要引入下层产物没有支持的新事实；所有判断都必须在 evidence_index 中引用下层事实产物。",
            "evidence_index 至少引用 chapters.yaml、characters/profiles 或 worldbuilding/ 中的一类条目。",
            "输出必须是 JSON 对象，字段包括 core_hooks、reader_expectations、story_structure、character_dynamics、worldbuilding_drivers、motifs_and_techniques、transferable_lessons、evidence_index、limitations、confidence。",
        )
    )
    user_prompt = "\n".join(
        (
            "请基于以下已压缩事实上下文生成作品画像。",
            "只允许概括写作模式、读者期待、人物动力、世界观驱动和可迁移技法；不要复述长篇正文。",
            _json_context(context),
        )
    )
    return system_prompt, user_prompt


def _json_context(context: Mapping[str, Any]) -> str:
    return json.dumps(
        context,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


__all__ = ["build_work_profile_prompt"]
