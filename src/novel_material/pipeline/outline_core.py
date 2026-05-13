"""大纲生成入口：结构 + 序列 + 节拍 + 钩子网络。

此模块包含 generate_outline 主函数，
调用各子模块完成大纲生成任务。

两阶段策略：
1. 全局一次：基于分层摘要池生成前提/主题/基调 + 幕/序列划分
2. per-sequence 循环：为每个序列独立生成 beats，上下文聚焦，输出量可控
"""
import sys
import yaml
import time
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm, get_last_call_finish_reason, get_call_details
from novel_material.infra.common import is_special_chapter_type
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.infra.progress import get_pipeline_logger, PipelineRunner

from novel_material.pipeline.outline_temp import (
    _save_acts_temp,
    _load_acts_temp,
    _save_sequence_beats_temp,
    _load_sequence_beats_temp,
    _save_outline_progress,
    _load_outline_progress,
    _cleanup_outline_temp_files,
)
from novel_material.pipeline.outline_stats import _extract_outline_stats
from novel_material.pipeline.outline_acts import _generate_acts_sequences, generate_simple_acts
from novel_material.pipeline.outline_beats import _generate_beats_for_sequence

logger = get_pipeline_logger()


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
    status = meta.get("status", "raw")

    # 读取章节索引
    chapter_index_file = novel_dir / "chapter_index.yaml"
    if not chapter_index_file.exists():
        logger.error(f"[{material_id}] chapter_index.yaml 不存在")
        return False

    with open(chapter_index_file, "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f) or []
    chapter_count = len(chapter_index)

    # 创建 PipelineRunner 记录运行历史
    runner = PipelineRunner(
        name="大纲生成",
        total_stages=3,  # 前提提炼 + 幕序列划分 + beats生成
        novel_dir=novel_dir,
        material_id=material_id,
        novel_info={"name": title, "chapter_count": chapter_count, "word_count": word_count}
    )
    wall_start = time.monotonic()

    # 输出小说基本信息
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")

    # 加载章节数据
    chapters_data = load_chapters_data(novel_dir)

    # 过滤特殊类型章节
    normal_chapters = [
        ch for ch in chapters_data
        if not is_special_chapter_type(ch.get("type", "normal"))
    ]
    filtered_count = len(chapters_data) - len(normal_chapters)
    if filtered_count > 0:
        logger.info(f"[{material_id}] 跳过 {filtered_count} 个特殊类型章节")

    # 统计大纲相关数据
    outline_stats = _extract_outline_stats(normal_chapters) if normal_chapters else {}
    high_tension_count = len(outline_stats.get("high_tension_chapters", []))
    suspense_count = len(outline_stats.get("suspense_chapters", []))
    logger.info(f"[{material_id}] 大纲统计: {high_tension_count} 个高张力章节, {suspense_count} 个悬念章节")

    if normal_chapters:
        context_text = build_summary_pool(normal_chapters, config["llm"]["outline_summary_tokens"], model)
        context_chars = len(context_text)
        context_label = f"章级摘要池（共 {len(normal_chapters)} 章）"
        logger.info(f"[{material_id}] 输入: {context_chars} 字符 | {context_label}")
    else:
        logger.warning(f"[{material_id}] 正文字数据不存在或为空，回退到原文前 5000 字")
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

    premise_base_len = len(get_call_details())

    result = {}
    try:
        result = call_llm(system_prompt_premise, user_prompt_premise, config, timeout_override=config["llm"]["outline_timeout"], context=f"{material_id} 前提提炼")
        logger.info(f"[{material_id}] 前提提炼完成: finish={get_last_call_finish_reason()}")
    except Exception as e:
        logger.error(f"[{material_id}] 前提提炼失败: {e}")
        logger.warning(f"[{material_id}] 使用默认值继续，不中断流程")
        result = {
            "premise": "未知",
            "structure_type": "三幕式",
            "total_acts": 3,
            "theme": [],
            "tone": []
        }

    # 将 premise 写入 meta
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    meta["premise"] = result.get("premise", "未知")
    meta["theme"] = result.get("theme", [])
    meta["tone"] = result.get("tone", [])
    meta["structure_type"] = result.get("structure_type", "三幕式")

    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    logger.info(f"[{material_id}] 已生成前提: {meta['premise']}")

    # 记录前提提炼阶段完成
    premise_elapsed = time.monotonic() - wall_start
    call_details = get_call_details()
    premise_tokens_in = sum(d.get("input_tokens", 0) for d in call_details[premise_base_len:])
    premise_tokens_out = sum(d.get("output_tokens", 0) for d in call_details[premise_base_len:])
    runner.record_stage_complete(
        stage_name="前提提炼",
        elapsed=premise_elapsed,
        api_calls=1,
        api_errors=0 if "premise" in result else 1,
        tokens_in=premise_tokens_in,
        tokens_out=premise_tokens_out
    )
    wall_start = time.monotonic()

    time.sleep(rate_limit)

    # ── 第二轮：生成幕 + 序列（不含 beats）（断点续传 + 容错）──
    acts = _load_acts_temp(outline_dir)
    if acts and any(act.get("sequences") for act in acts):
        logger.info(f"[{material_id}] 断点续传：加载已完成的幕/序列划分")
        runner.record_stage_complete(
            stage_name="幕序列划分(断点续传)",
            elapsed=0.0,
            api_calls=0,
            api_errors=0,
            tokens_in=0,
            tokens_out=0
        )
        wall_start = time.monotonic()
    else:
        acts_base_len = len(get_call_details())
        acts = []
        logger.info(f"[{material_id}] 生成幕/序列结构（共 {chapter_count} 章）...")
        try:
            acts = _generate_acts_sequences(chapter_count, meta, context_text, outline_stats, config, material_id=material_id)
            time.sleep(rate_limit)
            if not acts or not any(act.get("sequences") for act in acts):
                logger.warning(f"[{material_id}] LLM 返回空结构，使用简单划分")
                acts = generate_simple_acts(chapter_count, result.get("structure_type", "三幕式"))
        except Exception as e:
            logger.error(f"[{material_id}] 幕/序列生成失败: {e}")
            logger.warning(f"[{material_id}] 使用简单划分继续，不中断流程")
            acts = generate_simple_acts(chapter_count, result.get("structure_type", "三幕式"))

        _save_acts_temp(outline_dir, acts)
        logger.info(f"[{material_id}] 已保存幕/序列划分中间结果")

        acts_elapsed = time.monotonic() - wall_start
        call_details = get_call_details()
        acts_tokens_in = sum(d.get("input_tokens", 0) for d in call_details[acts_base_len:])
        acts_tokens_out = sum(d.get("output_tokens", 0) for d in call_details[acts_base_len:])
        runner.record_stage_complete(
            stage_name="幕序列划分",
            elapsed=acts_elapsed,
            api_calls=1,
            api_errors=0 if acts else 1,
            tokens_in=acts_tokens_in,
            tokens_out=acts_tokens_out
        )
        wall_start = time.monotonic()

    # ── 第三轮：逐序列生成 beats（每个序列容错，断点续传）──
    total_sequences = sum(len(act.get("sequences", [])) for act in acts)

    progress = _load_outline_progress(outline_dir)
    completed_seqs = progress.get("completed_sequences", [])

    if completed_seqs:
        prev_total = progress.get("total_sequences", 0)
        if prev_total == total_sequences:
            logger.info(f"[{material_id}] 断点续传：已完成 {len(completed_seqs)}/{total_sequences} 个序列")
        else:
            logger.warning(f"[{material_id}] acts 结构变化（{prev_total}→{total_sequences}序列），清理临时文件并重置进度")
            _cleanup_outline_temp_files(outline_dir)
            _save_acts_temp(outline_dir, acts)
            completed_seqs = []

    if progress_callback:
        progress_callback(len(completed_seqs), total_sequences, f"逐序列生成 beats（共 {total_sequences} 个）")
    else:
        logger.info(f"[{material_id}] 逐序列生成 beats（共 {total_sequences} 个序列）...")

    beats_base_len = len(get_call_details())

    beats_data = []
    seq_global = 0
    failed_sequences = 0

    for act in acts:
        for seq in act.get("sequences", []):
            seq_global += 1
            seq_title = seq.get("title", "")
            seq_key = f"{act['act_number']}_{seq['sequence_number']}"

            # 断点续传：跳过已完成的序列
            if seq_key in completed_seqs:
                beats = _load_sequence_beats_temp(outline_dir, act["act_number"], seq["sequence_number"]) or []
                seq["beats"] = beats
                for beat in beats:
                    beats_data.append({
                        "material_id": material_id,
                        "act": act["act_number"],
                        "sequence": seq["sequence_number"],
                        "beat": beat.get("beat_number", 0),
                        "title": beat.get("title", ""),
                        "chapter": beat.get("chapter", 0),
                        "description": beat.get("description", ""),
                        "tension": beat.get("tension", 1)
                    })
                if not progress_callback:
                    logger.info(f"[{material_id}] [{seq_global}/{total_sequences}] 跳过已完成: {seq_title}")
                continue

            if not progress_callback:
                logger.info(f"[{material_id}] [{seq_global}/{total_sequences}] {act.get('name', '')} / {seq_title}")

            beats = []
            try:
                beats = _generate_beats_for_sequence(
                    act_number=act["act_number"],
                    seq=seq,
                    chapters_data=normal_chapters,
                    model=model,
                    config=config,
                    material_id=material_id,
                )
            except Exception as e:
                logger.error(f"[{material_id}] 序列 {seq_global} beats 生成失败: {e}")
                logger.warning(f"[{material_id}] 跳过该序列，继续下一个")
                failed_sequences += 1

            seq["beats"] = beats

            if beats:
                _save_sequence_beats_temp(outline_dir, act["act_number"], seq["sequence_number"], beats)
                completed_seqs.append(seq_key)
                _save_outline_progress(outline_dir, completed_seqs, total_sequences)

                for beat in beats:
                    beats_data.append({
                        "material_id": material_id,
                        "act": act["act_number"],
                        "sequence": seq["sequence_number"],
                        "beat": beat.get("beat_number", 0),
                        "title": beat.get("title", ""),
                        "chapter": beat.get("chapter", 0),
                        "description": beat.get("description", ""),
                        "tension": beat.get("tension", 1)
                    })

            if progress_callback:
                if beats:
                    progress_callback(seq_global, total_sequences, f"{act.get('name', '')} / {seq_title}")
                else:
                    progress_callback(seq_global, total_sequences, f"[失败] {act.get('name', '')} / {seq_title}")

            if seq_global < total_sequences:
                time.sleep(rate_limit)

    if failed_sequences > 0:
        logger.warning(f"[{material_id}] 共有 {failed_sequences} 个序列 beats 生成失败")

    # Beats 质量统计
    if beats_data:
        tension_vals = [b.get("tension", 0) for b in beats_data if b.get("tension")]
        beats_per_seq = len(beats_data) / max(total_sequences, 1)
        logger.info(
            f"[{material_id}] Beats 统计: {len(beats_data)} 个节拍 | "
            f"每序列平均 {beats_per_seq:.1f} 个 | "
            f"张力范围 {min(tension_vals)}-{max(tension_vals)}"
        )

    beats_elapsed = time.monotonic() - wall_start
    call_details = get_call_details()
    beats_tokens_in = sum(d.get("input_tokens", 0) for d in call_details[beats_base_len:])
    beats_tokens_out = sum(d.get("output_tokens", 0) for d in call_details[beats_base_len:])
    runner.record_stage_complete(
        stage_name=f"Beats生成({total_sequences}序列)",
        elapsed=beats_elapsed,
        api_calls=total_sequences,
        api_errors=failed_sequences,
        tokens_in=beats_tokens_in,
        tokens_out=beats_tokens_out
    )

    # ── 写入输出文件 ──
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

    with open(outline_dir / "structure.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"acts": acts}, f, allow_unicode=True, default_flow_style=False)

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

    with open(outline_dir / "hooks_network.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"hooks": [], "subplots": []}, f, allow_unicode=True, default_flow_style=False)

    _cleanup_outline_temp_files(outline_dir)

    logger.info(
        f"[{material_id}] 大纲生成完成: {len(acts)}幕, {total_sequences}序列, {len(beats_data)}节拍"
        + (f" ({failed_sequences}序列失败)" if failed_sequences > 0 else "")
    )

    runner.save_history(status="success")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python outline_core.py <material_id>")
        sys.exit(1)

    generate_outline(sys.argv[1])