"""幕序列生成：基于章级摘要池生成幕/序列划分。

此模块包含幕序列生成函数，
供 outline_core.py 使用。
"""
from novel_material.infra.llm import call_llm, start_llm_telemetry
from novel_material.infra.progress import get_pipeline_logger
from novel_material.infra.llm_contracts import LLMResponseContractError, require_integer, require_mapping, require_mapping_list, require_string

logger = get_pipeline_logger()


def normalize_acts_response(payload: object, chapter_count: int) -> list[dict]:
    raw = payload if isinstance(payload, list) else require_mapping(payload, "outline.acts").get("acts")
    acts = require_mapping_list(raw, "outline.acts")
    for ai, act in enumerate(acts):
        base = f"outline.acts[{ai}]"
        for field in ("act_number", "chapter_start", "chapter_end"):
            act[field] = require_integer(act.get(field), f"{base}.{field}")
        act["name"] = require_string(act.get("name"), f"{base}.name")
        if not 1 <= act["chapter_start"] <= act["chapter_end"] <= chapter_count:
            raise LLMResponseContractError(base, "有效章节范围", act)
        sequences = require_mapping_list(act.get("sequences"), f"{base}.sequences")
        for si, seq in enumerate(sequences):
            path = f"{base}.sequences[{si}]"
            for field in ("sequence_number", "chapter_start", "chapter_end"):
                seq[field] = require_integer(seq.get(field), f"{path}.{field}")
            for field in ("title", "description"):
                seq[field] = require_string(seq.get(field), f"{path}.{field}")
            if not 1 <= seq["chapter_start"] <= seq["chapter_end"] <= chapter_count:
                raise LLMResponseContractError(path, "有效章节范围", seq)
        act["sequences"] = sequences
    return acts


def _generate_acts_sequences(
    chapter_count: int,
    meta: dict,
    context_text: str,
    outline_stats: dict,
    config: dict,
    material_id: str = "",
) -> list:
    """生成完整的幕/序列划分（章节范围，不含 beats）。

    仅生成幕和序列的章节范围与描述，beats 在第二阶段逐序列生成，
    避免一次输出 1000+ 条 beats JSON 导致必然截断的问题。
    """
    prefix = f"[{material_id}] " if material_id else ""
    system_prompt = """你是专业的小说结构分析师。请根据章节总数和小说类型，生成合理的幕/序列划分。
返回 JSON 格式：
{
  "acts": [
    {
      "act_number": 1,
      "name": "第一幕：建立",
      "chapter_start": 1,
      "chapter_end": 50,
      "sequences": [
        {
          "sequence_number": 1,
          "title": "序列标题",
          "chapter_start": 1,
          "chapter_end": 15,
          "description": "序列描述（50字内）"
        }
      ]
    }
  ]
}

注意：
1. 总幕数根据结构类型决定（三幕式=3幕，英雄之旅=4幕）
2. 每幕包含 2-5 个序列
3. 所有章节必须被覆盖，不要遗漏
4. 不需要包含 beats（节拍将在后续步骤单独生成）
5. 序列划分应考虑高潮章节分布，将高张力章节作为序列转折点"""

    # 构建统计信息文本
    tension_dist = outline_stats.get("tension_distribution", {})
    high_tension = outline_stats.get("high_tension_chapters", [])
    suspense = outline_stats.get("suspense_chapters", [])

    tension_lines = [f"  张力{k}: {v} 章" for k, v in tension_dist.items()]
    tension_text = "\n".join(tension_lines)

    # 高张力章节分组（避免列表太长）
    if len(high_tension) > 50:
        # 分组展示
        groups = []
        step = 20
        for i in range(0, len(high_tension), step):
            group = high_tension[i:i+step]
            groups.append(f"  {group[0]}-{group[-1]}: {group}")
        high_tension_text = "\n".join(groups[:5])  # 只展示前5组
    else:
        high_tension_text = ", ".join(map(str, high_tension[:50]))

    suspense_text = ", ".join(map(str, suspense[:50])) if suspense else "无"

    user_prompt = f"""小说信息：
- 类型：{meta.get('theme', ['未知'])}
- 基调：{meta.get('tone', ['未知'])}
- 总章节数：{chapter_count}
- 结构类型：{meta.get('structure_type', '三幕式')}

【张力分布】：
{tension_text}

【高张力章节】（张力≥4，高潮节点）：
{high_tension_text}

【悬念章节】（钩子节点）：
{suspense_text}

全书摘要参考：
{context_text}

请生成完整的幕/序列划分（仅需章节范围和描述，不需要 beats）。
序列划分应让高潮章节（高张力章节）成为序列的转折点或结尾。"""

    telemetry = start_llm_telemetry()
    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=4000, timeout_override=config["llm"]["outline_timeout"], context=f"{material_id} 幕序列划分")
    logger.info(f"{prefix}幕序列划分完成: finish={telemetry.last.get('finish_reason', '')}")
    return normalize_acts_response(result, chapter_count)


def generate_simple_acts(chapter_count: int, structure_type: str = "三幕式") -> list:
    """生成简单的幕/序列划分（LLM 失败时的兜底方案）。

    Args:
        chapter_count: 总章节数（必须 >= 1）
        structure_type: 结构类型

    Returns:
        简单划分的 acts 列表
    """
    # 边界保护：章节太少时用单一划分
    if chapter_count < 3:
        return [
            {
                "act_number": 1,
                "name": "全书",
                "chapter_start": 1,
                "chapter_end": chapter_count,
                "sequences": [{
                    "sequence_number": 1,
                    "title": "完整故事",
                    "chapter_start": 1,
                    "chapter_end": chapter_count,
                    "description": "短篇故事"
                }]
            }
        ]

    # 三幕式划分
    if structure_type == "三幕式":
        act1_end = max(1, int(chapter_count * 0.25))  # 至少 1 章
        act2_end = max(act1_end + 1, int(chapter_count * 0.75))  # 至少 act1_end + 1
        return [
            {
                "act_number": 1,
                "name": "第一幕：建立",
                "chapter_start": 1,
                "chapter_end": act1_end,
                "sequences": [{"sequence_number": 1, "title": "开篇", "chapter_start": 1, "chapter_end": act1_end, "description": "故事建立"}]
            },
            {
                "act_number": 2,
                "name": "第二幕：对抗",
                "chapter_start": act1_end + 1,
                "chapter_end": act2_end,
                "sequences": [{"sequence_number": 2, "title": "发展", "chapter_start": act1_end + 1, "chapter_end": act2_end, "description": "冲突发展"}]
            },
            {
                "act_number": 3,
                "name": "第三幕：解决",
                "chapter_start": act2_end + 1,
                "chapter_end": chapter_count,
                "sequences": [{"sequence_number": 3, "title": "结局", "chapter_start": act2_end + 1, "chapter_end": chapter_count, "description": "故事结局"}]
            }
        ]
    else:
        # 其他类型：简单等分
        return [
            {
                "act_number": 1,
                "name": "第一部分",
                "chapter_start": 1,
                "chapter_end": chapter_count,
                "sequences": [{"sequence_number": 1, "title": "全书", "chapter_start": 1, "chapter_end": chapter_count, "description": "完整故事"}]
            }
        ]


__all__ = ["_generate_acts_sequences", "generate_simple_acts"]
