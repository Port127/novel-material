"""大纲生成：LLM 基于章级摘要池生成故事大纲结构（幕/序列/节拍/钩子网络）。

注意：此脚本必须在 analyze 完成后运行，需要 chapters.yaml 作为全局视角输入。

规模适配：
- 摘要池采用分层均匀采样（> 200 章时），确保全书首尾及中间均有代表
- beats 生成拆分为 per-sequence 循环：每个序列独立调用 LLM，避免一次性输出 1000+ 条被截断

统计驱动：
- 张力分布：识别高潮章节，指导序列划分
- 悬念分布：识别钩子节点，指导节奏控制
"""
import sys
import yaml
import time
from pathlib import Path
from collections.abc import Callable
from collections import Counter

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm, get_last_call_finish_reason
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()


def _extract_outline_stats(chapters_data: list) -> dict:
    """统计大纲相关数据：张力分布、悬念章节、章节功能。

    返回：
        dict: {
            "tension_distribution": {张力等级: 章数},
            "high_tension_chapters": [高张力章节号列表],
            "suspense_chapters": [悬念章节号列表],
            "function_distribution": {功能: 章数}
        }
    """
    tension_counts = Counter()
    high_tension_chapters = []  # 张力 >= 4
    suspense_chapters = []  # 有"悬念"功能的章节
    function_counts = Counter()

    for ch in chapters_data:
        ch_num = ch.get("chapter", 0)
        tension = ch.get("tension_level", 0)
        functions = ch.get("chapter_functions", [])

        tension_counts[tension] += 1

        if tension >= 4:
            high_tension_chapters.append(ch_num)

        if any("悬念" in f for f in functions):
            suspense_chapters.append(ch_num)

        function_counts.update(functions)

    return {
        "tension_distribution": dict(sorted(tension_counts.items())),
        "high_tension_chapters": sorted(high_tension_chapters),
        "suspense_chapters": sorted(suspense_chapters),
        "function_distribution": dict(function_counts.most_common(20))
    }


# ============================================================
# 第一阶段：生成幕 + 序列（不含 beats）
# ============================================================

def _generate_acts_sequences(
    chapter_count: int,
    meta: dict,
    context_text: str,
    outline_stats: dict,
    config: dict
) -> list:
    """生成完整的幕/序列划分（章节范围，不含 beats）。

    仅生成幕和序列的章节范围与描述，beats 在第二阶段逐序列生成，
    避免一次输出 1000+ 条 beats JSON 导致必然截断的问题。
    """
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

    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=4000, timeout_override=config["llm"]["outline_timeout"], context="幕序列划分")
    logger.info(f"幕序列划分完成: finish={get_last_call_finish_reason()}")
    # 兼容 LLM 直接返回数组的情况
    if isinstance(result, list):
        logger.warning("幕序列划分返回裸数组，自动适配")
        return result
    return result.get("acts", [])


# ============================================================
# 第二阶段：逐序列生成 beats
# ============================================================

def _generate_beats_for_sequence(
    act_number: int,
    seq: dict,
    chapters_data: list,
    model: str,
    config: dict,
) -> list:
    """为单个序列生成 beats（节拍）。

    每次只处理一个序列（通常 30-150 章），上下文聚焦，输出量可控（5-15 条 beats），
    彻底避免"要求 LLM 一次输出 1600 条 beats"的结构性截断问题。
    """
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

    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=2000, timeout_override=config["llm"]["outline_timeout"], context=f"beats#{seq.get('sequence_number', '?')}")
    logger.debug(f"beats#{seq.get('sequence_number', '?')}: finish={get_last_call_finish_reason()}")
    # 兼容 LLM 直接返回数组的情况
    if isinstance(result, list):
        logger.warning(f"beats#{seq.get('sequence_number', '?')} 返回裸数组，自动适配")
        return result
    return result.get("beats", [])


# ============================================================
# 主函数
# ============================================================

def generate_outline(material_id, progress_callback: Callable[[int, int, str], None] | None = None, provider: str | None = None) -> bool:
    """生成大纲：结构 + 序列 + 节拍 + 钩子网络。

    两阶段策略：
    1. 全局一次：基于分层摘要池生成前提/主题/基调 + 幕/序列划分
    2. per-sequence 循环：为每个序列独立生成 beats，上下文聚焦，输出量可控

    容错策略：
    - 每轮 LLM 调用失败时使用默认值继续
    - 序列 beats 生成失败时跳过该序列，继续下一个

    参数：
        material_id: 素材 ID
        progress_callback: 可选进度回调函数 (done: int, total: int, desc: str) -> None
        provider: 服务商名称（可选，不指定则使用默认配置）

    返回：
        True 表示成功，False 表示失败
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    config = load_config(provider)
    model = config["llm"]["model"]
    outline_dir = novel_dir / "outline"
    outline_dir.mkdir(exist_ok=True)

    # 加载小说基本信息
    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "?")

    # 读取章节索引
    chapter_index_file = novel_dir / "chapter_index.yaml"
    if not chapter_index_file.exists():
        logger.error(f"[{material_id}] chapter_index.yaml 不存在")
        return False

    with open(chapter_index_file, "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f) or []
    chapter_count = len(chapter_index)

    # 输出小说基本信息
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")

    # 加载章节数据（优先从 chapters/ 目录，兜底 chapters.yaml）
    chapters_data = load_chapters_data(novel_dir)

    # 统计大纲相关数据
    outline_stats = _extract_outline_stats(chapters_data) if chapters_data else {}
    high_tension_count = len(outline_stats.get("high_tension_chapters", []))
    suspense_count = len(outline_stats.get("suspense_chapters", []))
    logger.info(f"[{material_id}] 大纲统计: {high_tension_count} 个高张力章节, {suspense_count} 个悬念章节")

    if chapters_data:
        context_text = build_summary_pool(chapters_data, config["llm"]["outline_summary_tokens"], model)
        context_chars = len(context_text)
        context_label = f"章级摘要池（共 {len(chapters_data)} 章）"
        logger.info(f"[{material_id}] 输入: {context_chars} 字符 | {context_label}")
    else:
        logger.warning(f"[{material_id}] 章节数据不存在或为空，回退到原文前 5000 字（质量受限）")
        with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
            context_text = f.read()[:5000]
        context_chars = len(context_text)
        context_label = "原文摘录（前 5000 字）"
        logger.info(f"[{material_id}] 输入: {context_chars} 字符 | {context_label}")

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    # ── 第一轮：提炼前提 + 主题 + 基调（容错）──
    system_prompt_premise = """你是专业的小说结构分析师。请根据提供的内容，生成以下 JSON：
{
  "premise": "一句话核心前提（50字以内）",
  "structure_type": "三幕式/英雄之旅/多线叙事",
  "total_acts": 3,
  "theme": ["主题1", "主题2"],
  "tone": ["基调1", "基调2"]
}"""

    user_prompt_premise = f"""请分析以下小说，提炼核心前提和整体结构：

{context_label}：
{context_text}

返回 JSON 格式如上。"""

    result = {}
    try:
        result = call_llm(system_prompt_premise, user_prompt_premise, config, timeout_override=config["llm"]["outline_timeout"], context="前提提炼")
        logger.info(f"前提提炼完成: finish={get_last_call_finish_reason()}")
    except Exception as e:
        logger.error(f"前提提炼失败: {e}")
        logger.warning("使用默认值继续，不中断流程")
        result = {
            "premise": "未知",
            "structure_type": "三幕式",
            "total_acts": 3,
            "theme": [],
            "tone": []
        }

    # 将 premise 写入 meta
    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    meta["premise"] = result.get("premise", "未知")
    meta["theme"] = result.get("theme", [])
    meta["tone"] = result.get("tone", [])
    meta["structure_type"] = result.get("structure_type", "三幕式")

    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    logger.info(f"已生成前提: {meta['premise']}")
    time.sleep(rate_limit)

    # ── 第二轮：生成幕 + 序列（不含 beats）（容错）──
    logger.info(f"生成幕/序列结构（共 {chapter_count} 章）...")
    acts = []
    try:
        acts = _generate_acts_sequences(chapter_count, meta, context_text, outline_stats, config)
        time.sleep(rate_limit)
        # 检查返回是否有效（空列表或无序列视为失败）
        if not acts or not any(act.get("sequences") for act in acts):
            logger.warning("LLM 返回空结构，使用简单划分")
            acts = generate_simple_acts(chapter_count, result.get("structure_type", "三幕式"))
    except Exception as e:
        logger.error(f"幕/序列生成失败: {e}")
        logger.warning("使用简单划分继续，不中断流程")
        acts = generate_simple_acts(chapter_count, result.get("structure_type", "三幕式"))

    # ── 第三轮：逐序列生成 beats（每个序列容错）──
    total_sequences = sum(len(act.get("sequences", [])) for act in acts)
    if progress_callback:
        progress_callback(0, total_sequences, f"逐序列生成 beats（共 {total_sequences} 个）")
    else:
        logger.info(f"逐序列生成 beats（共 {total_sequences} 个序列）...")

    beats_data = []
    seq_global = 0
    failed_sequences = 0

    for act in acts:
        for seq in act.get("sequences", []):
            seq_global += 1
            seq_title = seq.get("title", "")

            # 序列开始时的日志（非回调模式）
            if not progress_callback:
                logger.info(f"  [{seq_global}/{total_sequences}] {act.get('name', '')} / {seq_title}")

            # 每个序列独立容错
            beats = []
            try:
                beats = _generate_beats_for_sequence(
                    act_number=act["act_number"],
                    seq=seq,
                    chapters_data=chapters_data,
                    model=model,
                    config=config,
                )
            except Exception as e:
                logger.error(f"序列 {seq_global} beats 生成失败: {e}")
                logger.warning("跳过该序列，继续下一个")
                failed_sequences += 1

            seq["beats"] = beats
            for beat in beats:
                beats_data.append({
                    "material_id": material_id,
                    "act": act["act_number"],
                    "sequence": seq["sequence_number"],
                    "beat": beat["beat_number"],
                    "title": beat.get("title", ""),
                    "chapter": beat.get("chapter", 0),
                    "description": beat.get("description", ""),
                    "tension": beat.get("tension", 1)
                })

            # 进度更新：在序列完成后更新
            if progress_callback:
                progress_callback(seq_global, total_sequences, f"{act.get('name', '')} / {seq_title}")

            if seq_global < total_sequences:
                time.sleep(rate_limit)

    if failed_sequences > 0:
        logger.warning(f"共有 {failed_sequences} 个序列 beats 生成失败")

    # Beats 质量统计
    if beats_data:
        tension_vals = [b.get("tension", 0) for b in beats_data if b.get("tension")]
        beats_per_seq = len(beats_data) / max(total_sequences, 1)
        logger.info(
            f"Beats 统计: {len(beats_data)} 个节拍 | "
            f"每序列平均 {beats_per_seq:.1f} 个 | "
            f"张力范围 {min(tension_vals)}-{max(tension_vals)}"
        )

    # ── 写入输出文件 ──

    # _index.yaml
    index_data = {
        "structure_type": meta.get("structure_type", "三幕式"),
        "act_count": len(acts),
        "sequence_count": total_sequences,
        "sequence_failed": failed_sequences,
        "hook_count": 0,
        "subplot_count": 0,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    with open(outline_dir / "_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(index_data, f, allow_unicode=True, default_flow_style=False)

    # structure.yaml（含 beats）
    with open(outline_dir / "structure.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"acts": acts}, f, allow_unicode=True, default_flow_style=False)

    # sequences.yaml（供 sync_db 使用）
    sequences_data = []
    for act in acts:
        for seq in act.get("sequences", []):
            sequences_data.append({
                "material_id": material_id,
                "act": act["act_number"],
                "sequence": seq["sequence_number"],
                "title": seq.get("title", ""),
                "chapters_start": seq.get("chapter_start", 0),
                "chapters_end": seq.get("chapter_end", 0),
                "description": seq.get("description", "")
            })

    with open(outline_dir / "sequences.yaml", "w", encoding="utf-8") as f:
        yaml.dump(sequences_data, f, allow_unicode=True, default_flow_style=False)

    with open(outline_dir / "beats.yaml", "w", encoding="utf-8") as f:
        yaml.dump(beats_data, f, allow_unicode=True, default_flow_style=False)

    # 空钩子网络（待 refine 阶段补充）
    with open(outline_dir / "hooks_network.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"hooks": [], "subplots": []}, f, allow_unicode=True, default_flow_style=False)

    logger.info(
        f"[{material_id}] 大纲生成完成: {len(acts)}幕, {total_sequences}序列, {len(beats_data)}节拍"
        + (f" ({failed_sequences}序列失败)" if failed_sequences > 0 else "")
    )

    return True


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python outline.py <material_id>")
        sys.exit(1)

    generate_outline(sys.argv[1])