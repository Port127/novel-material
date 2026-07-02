"""核心人物小传 repair 调用。"""

from __future__ import annotations

import json
from typing import Any

from novel_material.infra.llm import call_llm
from novel_material.pipeline.characters_biography import normalize_biography_response


def repair_core_biography_profile(
    *,
    raw_profile: dict[str, Any],
    issues: tuple[str, ...],
    candidate_names: set[str],
    config: dict,
    material_id: str,
    context_label: str,
    context_text: str,
) -> dict[str, Any]:
    """对单个核心人物小传做格式修复，返回 strict-normalized profile。"""
    system_prompt = """你是小说人物档案 JSON 修复器。只修复结构和缺失字段，不新增候选名单之外的人物。
必须返回 {"characters": [{"name": "角色名"}]} 形态，数组中只能有一个人物。"""
    user_prompt = f"""请修复以下人物档案，使其符合完整小传 schema。

候选名单：{sorted(candidate_names)}
错误列表：{list(issues)}

原始档案：
{json.dumps(raw_profile, ensure_ascii=False)}

{context_label}：
{context_text}
"""
    response = call_llm(
        system_prompt,
        user_prompt,
        config,
        max_tokens_override=4000,
        timeout_override=config["llm"]["characters_timeout"],
        context=f"{material_id} 人物小传repair#{raw_profile.get('name', 'unknown')}",
    )
    normalized = normalize_biography_response(response, candidate_names)
    repaired = dict(normalized[0])
    repaired["source_quality"] = "llm_repaired"
    repaired["repair_attempts"] = 1
    return repaired


__all__ = ["repair_core_biography_profile"]
