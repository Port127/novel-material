"""分批提取人物详情：统计驱动的分层处理。

此模块包含分批提取人物详情的函数，
供 characters_core.py 使用。
"""
import time

from novel_material.infra.llm import call_llm
from novel_material.infra.progress import get_pipeline_logger
from novel_material.pipeline.characters_biography import (
    normalize_biography_candidates,
    normalize_biography_response,
)
from novel_material.pipeline.characters_quality import mark_schema_issue
from novel_material.pipeline.characters_repair import repair_core_biography_profile
from novel_material.pipeline.characters_stats import CHARACTER_BATCH_SIZE
from novel_material.pipeline.characters_profile import _build_basic_profile_from_stats
from novel_material.infra.llm_contracts import LLMResponseContractError, require_mapping, require_mapping_list, require_string

logger = get_pipeline_logger()


def normalize_characters_response(payload: object, candidate_names: set[str]) -> list[dict]:
    raw = payload if isinstance(payload, list) else require_mapping(payload, "characters").get("characters")
    characters = require_mapping_list(raw, "characters")
    for index, character in enumerate(characters):
        path = f"characters[{index}]"
        name = require_string(character.get("name"), f"{path}.name")
        if name not in candidate_names:
            raise LLMResponseContractError(f"{path}.name", "候选名单中的字符串", name)
        for field in ("relationships", "key_events"):
            if character.get(field) is not None:
                character[field] = require_mapping_list(character[field], f"{path}.{field}")
    return characters


def _extract_character_batch(
    candidates: list[tuple[str, int]],
    role_tier: str,
    context_text: str,
    context_label: str,
    meta: dict,
    config: dict,
    material_id: str = "",
    batch_size: int | None = None,
    chapters_data: list | None = None,
) -> list[dict]:
    """分批调用LLM，为已筛选的候选人补充档案详情。

    注意：候选人名单已由出场统计确定，LLM只需补充详情，不需要"发现"人物。
    若LLM调用失败，使用出场统计生成基础档案兜底。

    Args:
        candidates: 候选人列表 [(name, count), ...]
        role_tier: 角色层级 "core"/"supporting"/"minor"
        context_text: 分析上下文（摘要池）
        context_label: 上下文标签
        meta: 小说元数据
        config: LLM配置
        material_id: 素材ID
        batch_size: 每批处理数量，默认 CHARACTER_BATCH_SIZE
        chapters_data: 章节数据（用于兜底时生成完整档案）

    Returns:
        list[dict]: 人物档案列表
    """
    if not candidates:
        return []

    if batch_size is None:
        llm_config = config.get("llm", {})
        if role_tier == "core":
            batch_size = int(llm_config.get("core_character_batch_size", 2))
        elif role_tier == "supporting":
            batch_size = int(
                llm_config.get("supporting_character_batch_size", CHARACTER_BATCH_SIZE)
            )
        else:
            batch_size = int(
                llm_config.get("minor_character_batch_size", CHARACTER_BATCH_SIZE)
            )

    prefix = f"[{material_id}] " if material_id else ""
    role_mapping = {
        "core": ("protagonist", "antagonist", "supporting"),
        "supporting": ("supporting",),
        "minor": ("minor",)
    }
    valid_roles = role_mapping.get(role_tier, ("minor",))

    # 根据角色层级构建不同的prompt
    if role_tier == "core":
        system_prompt = """你是专业的小说人物分析师。请为以下已确认的核心人物补充完整档案，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名（必须与输入一致）",
      "role": "protagonist/antagonist/supporting",
      "archetype": "英雄/导师/伙伴/反派/隐士/复仇者/守护者/野心家",
      "moral_spectrum": "善良/灰色/邪恶",
      "identity": "角色身份与社会位置",
      "life_summary": "压缩小传：经历、选择与代价",
      "external_goal": "外在目标",
      "internal_need": "内在需求",
      "fear": "恐惧",
      "fatal_flaw": "致命缺陷",
      "contradiction": "人物核心矛盾",
      "arc_stages": [{"stage": "opening/development/turning/climax/resolution", "change": "阶段变化", "evidence": {"chapters": [1]}}],
      "description": "角色描述（100字）",
      "arc_summary": "角色弧线概述（50字）",
      "narrative_function": "在故事中的功能",
      "psychology": {
        "fatal_flaw": "致命弱点",
        "obsession": "执念/目标",
        "soft_spot": "软肋",
        "motivation": "驱动力"
      },
      "first_appearance_chapter": 1,
      "key_events": [{"chapter": 1, "description": "关键事件"}],
      "relationships": [{"character": "角色名", "dynamic": "关系动态", "relationship": "兼容旧字段", "nature": "ally/enemy/romance/mentor/rival", "evidence": {"chapters": [2]}}],
      "habits": ["习惯或动作"],
      "speech_style": "语言风格",
      "interaction_patterns": ["互动模式"],
      "key_scenes": [{"chapter": 1, "event": "关键场景", "function": "塑造功能"}],
      "craft_notes": [{"technique": "写作手法", "boundary": "借鉴边界"}],
      "confidence": 0.86,
      "basis": "fact/inference"
    }
  ]
}

注意：
1. 必须为输入名单中的每个角色返回档案，不能遗漏
2. role 根据剧情重要性选择（主角用 protagonist，反派用 antagonist，其他用 supporting）
3. key_events 按重要性排序，最多 10 个
4. relationships 用中文描述
5. 每项分析必须标明事实依据或推断，basis 只能写 fact 或 inference
6. key_scenes 必须包含章节号 chapter
7. 不知道时写结构化不适用原因，不得留空"""
    elif role_tier == "supporting":
        system_prompt = """你是专业的小说人物分析师。请为以下已确认的配角补充标准档案，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名（必须与输入一致）",
      "role": "supporting",
      "description": "角色描述（50字）",
      "narrative_function": "在故事中的功能",
      "first_appearance_chapter": 1,
      "key_events": [{"chapter": 1, "description": "关键事件"}],
      "relationships": [{"character": "角色名", "relationship": "关系"}]
    }
  ]
}

注意：
1. 必须为输入名单中的每个角色返回档案，不能遗漏
2. key_events 最多 5 个
3. relationships 用中文描述"""
    else:  # minor
        system_prompt = """你是专业的小说人物分析师。请为以下已确认的次要角色补充精简档案，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名（必须与输入一致）",
      "role": "minor",
      "description": "角色描述（30字）",
      "narrative_function": "在故事中的功能（简述）",
      "first_appearance_chapter": 1,
      "relationships": [{"character": "角色名", "relationship": "关系"}]
    }
  ]
}

注意：
1. 必须为输入名单中的每个角色返回档案，不能遗漏
2. 档案精简，不需要 key_events"""

    all_characters = []
    total_batches = (len(candidates) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, len(candidates))
        batch_candidates = candidates[batch_start:batch_end]

        # 构建名单文本
        names_list = [f"{name}（{count}章）" for name, count in batch_candidates]
        names_text = "\n".join(names_list)

        user_prompt = f"""请为以下角色补充档案：

类型：{meta.get('theme', ['未知'])}

【待处理角色名单】（共 {len(batch_candidates)} 人）：
{names_text}

{context_label}：
{context_text}

请返回 JSON 格式如上，必须包含名单中每个角色的档案。"""

        try:
            result = call_llm(
                system_prompt, user_prompt, config,
                max_tokens_override=4000,
                timeout_override=config["llm"]["characters_timeout"],
                context=f"{material_id} 人物#{role_tier}批次{batch_idx + 1}"
            )

            # 验证返回的人物是否在候选名单中
            candidate_names = {name for name, _ in batch_candidates}
            if role_tier == "core":
                normalized_result = normalize_biography_candidates(result, candidate_names)
                characters = list(normalized_result.valid_profiles)
                candidate_counts = dict(batch_candidates)
                repair_attempts = int(
                    config["llm"].get("character_repair_max_attempts", 1)
                )
                if repair_attempts > 0:
                    for invalid in normalized_result.invalid_profiles:
                        if invalid.name not in candidate_names:
                            continue
                        try:
                            characters.append(
                                repair_core_biography_profile(
                                    raw_profile=invalid.raw,
                                    issues=invalid.issues,
                                    candidate_names={invalid.name},
                                    config=config,
                                    material_id=material_id,
                                    context_label=context_label,
                                    context_text=context_text,
                                )
                            )
                        except Exception as repair_error:
                            logger.error(
                                f"{prefix}核心人物 {invalid.name} repair 失败: {repair_error}"
                            )
                            count = candidate_counts.get(invalid.name, 0)
                            fallback = _build_basic_profile_from_stats(
                                invalid.name,
                                count,
                                valid_roles[0],
                                chapters_data or [],
                            )
                            fallback = mark_schema_issue(
                                fallback,
                                issue="; ".join(invalid.issues),
                                level="partial",
                                source_quality="llm_partial",
                                repair_attempts=repair_attempts,
                            )
                            characters.append(fallback)
                for missing_name in normalized_result.missing_names:
                    count = candidate_counts.get(missing_name, 0)
                    fallback = _build_basic_profile_from_stats(
                        missing_name,
                        count,
                        valid_roles[0],
                        chapters_data or [],
                    )
                    fallback = mark_schema_issue(
                        fallback,
                        issue="LLM 未返回该核心人物",
                        level="fallback",
                        source_quality="stats_seeded",
                        repair_attempts=0,
                    )
                    characters.append(fallback)
            else:
                characters = normalize_characters_response(result, candidate_names)
            for ch in characters:
                ch_name = ch.get("name")
                if ch_name in candidate_names:
                    all_characters.append(ch)
                else:
                    logger.warning(f"{prefix}批次{batch_idx + 1}: LLM返回了非候选人物 '{ch_name}'，跳过")

            logger.info(
                f"{prefix}批次{batch_idx + 1}/{total_batches}: "
                f"返回 {len(characters)} 人，有效 {len([ch for ch in characters if ch.get('name') in candidate_names])} 人"
            )

        except Exception as e:
            error_kind = "schema_invalid" if isinstance(e, LLMResponseContractError) else "LLM调用失败"
            logger.error(f"{prefix}批次{batch_idx + 1} {error_kind}: {e}")
            logger.warning(f"{prefix}使用出场统计生成基础档案兜底")
            # 兜底：生成基础档案
            for name, count in batch_candidates:
                if chapters_data:
                    profile = _build_basic_profile_from_stats(name, count, valid_roles[0], chapters_data)
                else:
                    profile = {
                        "name": name,
                        "role": valid_roles[0],
                        "description": f"出场 {count} 章。",
                        "first_appearance_chapter": None,
                        "narrative_function": "待补充",
                        "appearance_count": count,
                        "relationships": []
                    }
                all_characters.append(profile)

        # 批次间等待（避免rate limit）
        if batch_idx < total_batches - 1:
            time.sleep(config["llm"].get("rate_limit_seconds", 1))

    return all_characters


__all__ = ["_extract_character_batch"]
