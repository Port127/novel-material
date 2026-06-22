"""节拍生成：为单个序列生成 beats（节拍）。

此模块包含逐序列生成节拍的函数，
供 outline_core.py 使用。
"""
from novel_material.infra.llm import call_llm, start_llm_telemetry
from novel_material.infra.progress import get_pipeline_logger
from novel_material.pipeline.loader import build_summary_pool

logger = get_pipeline_logger()


def _generate_beats_for_sequence(
    act_number: int,
    seq: dict,
    chapters_data: list,
    model: str,
    config: dict,
    material_id: str = "",
) -> list:
    """为单个序列生成 beats（节拍）。

    每次只处理一个序列（通常 30-150 章），上下文聚焦，输出量可控（5-15 条 beats），
    彻底避免"要求 LLM 一次输出 1600 条 beats"的结构性截断问题。
    """
    prefix = f"[{material_id}] " if material_id else ""
    seq_start = seq.get("chapter_start", 0)
    seq_end = seq.get("chapter_end", 0)

    # 筛选本序列范围内的章节摘要
    seq_chapters = [
        ch for ch in chapters_data
        if isinstance(ch.get("chapter"), int) and seq_start <= ch["chapter"] <= seq_end
    ]

    # 统计序列内张力分布
    seq_tension = {}
    seq_high_tension = []
    for ch in seq_chapters:
        tension = ch.get("tension_level", 0)
        seq_tension[tension] = seq_tension.get(tension, 0) + 1
        if tension >= 4:
            seq_high_tension.append(ch.get("chapter", 0))

    seq_context = build_summary_pool(seq_chapters, config["llm"]["outline_seq_summary_tokens"], model, force_full=True) if seq_chapters else ""

    system_prompt = """你是专业的小说结构分析师。请为指定序列生成节拍（beats）列表。
返回 JSON 格式：
{
  "beats": [
    {
      "beat_number": 1,
      "title": "节拍标题",
      "chapter": 1,
      "description": "节拍描述（30字内）",
      "tension": 1
    }
  ]
}

注意：
1. 每个序列生成 3-10 个节拍（根据序列长度决定）
2. 节拍 tension 从 1-5，应与该章节的实际张力一致
3. chapter 填写该节拍对应的最关键章节号
4. 节拍应覆盖序列的开头、中间和结尾
5. 高张力章节（张力≥4）应是序列内的关键转折点"""

    # 构建序列内统计文本
    seq_tension_text = ", ".join([f"张力{k}:{v}章" for k, v in sorted(seq_tension.items())])
    seq_high_text = ", ".join(map(str, seq_high_tension[:20])) if seq_high_tension else "无"

    chapter_range = f"第 {seq_start}-{seq_end} 章（共 {seq_end - seq_start + 1} 章）"
    user_prompt = f"""序列信息：
- 第 {act_number} 幕 / 序列 {seq.get('sequence_number', '?')}
- 标题：{seq.get('title', '')}
- 章节范围：{chapter_range}
- 序列描述：{seq.get('description', '')}

【序列内张力分布】：
{seq_tension_text}

【序列内高张力章节】（张力≥4）：
{seq_high_text}

本序列章节摘要：
{seq_context if seq_context else '（摘要暂缺，请根据序列描述推断）'}

请为此序列生成节拍列表。
节拍的 tension 值应与章节实际张力一致，高张力章节应是关键节拍。"""

    telemetry = start_llm_telemetry()
    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=2000, timeout_override=config["llm"]["outline_timeout"], context=f"{material_id} beats#{seq.get('sequence_number', '?')}")
    logger.debug(f"{prefix}beats#{seq.get('sequence_number', '?')}: finish={telemetry.last.get('finish_reason', '')}")
    # 兼容 LLM 直接返回数组的情况
    if isinstance(result, list):
        logger.warning(f"{prefix}beats#{seq.get('sequence_number', '?')} 返回裸数组，自动适配")
        return result
    return result.get("beats", [])


__all__ = ["_generate_beats_for_sequence"]
