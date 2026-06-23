"""大纲生成业务逻辑函数。

此模块提供大纲生成过程中的核心业务逻辑：
- 前提提炼（LLM调用）
- 幕序列生成（含容错）
- Beats生成循环（含断点续传、进度追踪）
- 初始化与上下文构建
"""
import time
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm, start_llm_telemetry
from novel_material.infra.common import is_special_chapter_type
from novel_material.infra.progress import get_pipeline_logger, PipelineRunner
from novel_material.infra.llm_contracts import (
    LLMResponseContractError,
    require_integer,
    require_mapping,
    require_string,
    require_string_list,
)
from novel_material.pipeline.progress import OUTLINE_STAGES
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.pipeline.outline_io import (
    load_meta,
    load_chapter_index,
    load_source_text,
    save_meta_with_premise,
    save_outline_files,
    build_sequences_data,
)
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


def default_premise_response() -> dict:
    return {"premise": "未知", "structure_type": "三幕式", "total_acts": 3, "theme": [], "tone": []}


def normalize_premise_response(payload: object) -> dict:
    result = dict(require_mapping(payload, "outline.premise"))
    result["premise"] = require_string(result.get("premise"), "outline.premise.premise")
    result["structure_type"] = require_string(result.get("structure_type"), "outline.premise.structure_type")
    result["total_acts"] = require_integer(result.get("total_acts"), "outline.premise.total_acts")
    if result["total_acts"] < 1:
        raise LLMResponseContractError("outline.premise.total_acts", "正整数", result["total_acts"])
    result["theme"] = require_string_list(result.get("theme"), "outline.premise.theme")
    result["tone"] = require_string_list(result.get("tone"), "outline.premise.tone")
    return result


def extract_premise(
    context_text: str,
    context_label: str,
    config: dict,
    material_id: str = "",
) -> dict:
    """提炼前提、主题、基调。

    Args:
        context_text: 上下文文本
        context_label: 上下文标签（用于日志）
        config: 配置字典
        material_id: 素材ID

    Returns:
        前提数据字典，包含 premise, structure_type, total_acts, theme, tone
    """
    system_prompt = """你是专业的小说结构分析师。请根据提供的内容，生成以下 JSON：
{
  "premise": "一句话核心前提（50字以内）",
  "structure_type": "三幕式/英雄之旅/多线叙事",
  "total_acts": 3,
  "theme": ["主题1", "主题2"],
  "tone": ["基调1", "基调2"]
}"""

    user_prompt = f"""请分析以下小说，提炼核心前提和整体结构：

{context_label}：
{context_text}

返回 JSON 格式如上。"""

    result = {}
    telemetry = start_llm_telemetry()
    try:
        result = normalize_premise_response(call_llm(
            system_prompt,
            user_prompt,
            config,
            timeout_override=config["llm"]["outline_timeout"],
            context=f"{material_id} 前提提炼",
        ))
        logger.info(f"[{material_id}] 前提提炼完成: finish={telemetry.last.get('finish_reason', '')}")
    except Exception as e:
        error_kind = "schema_invalid" if isinstance(e, LLMResponseContractError) else "调用失败"
        logger.error(f"[{material_id}] 前提提炼 {error_kind}: {e}")
        logger.warning(f"[{material_id}] 使用默认值继续，不中断流程")
        result = default_premise_response()

    return result


def generate_acts_with_fallback(
    chapter_count: int,
    meta: dict,
    context_text: str,
    outline_stats: dict,
    config: dict,
    outline_dir: Path,
    material_id: str = "",
) -> tuple[list, bool]:
    """生成幕/序列划分（含断点续传和容错）。

    Args:
        chapter_count: 章节总数
        meta: meta 字典
        context_text: 上下文文本
        outline_stats: 大纲统计数据
        config: 配置字典
        outline_dir: 大纲目录路径
        material_id: 素材ID

    Returns:
        (acts, from_cache) 元组：
        - acts: 幕数据列表
        - from_cache: 是否从缓存加载
    """
    # 尝试从缓存加载
    acts = _load_acts_temp(outline_dir)
    if acts and any(act.get("sequences") for act in acts):
        logger.info(f"[{material_id}] 断点续传：加载已完成的幕/序列划分")
        return acts, True

    # 生成新的幕/序列
    logger.info(f"[{material_id}] 生成幕/序列结构（共 {chapter_count} 章）...")
    structure_type = meta.get("structure_type", "三幕式")

    try:
        acts = _generate_acts_sequences(
            chapter_count, meta, context_text, outline_stats, config, material_id=material_id
        )
        if not acts or not any(act.get("sequences") for act in acts):
            logger.warning(f"[{material_id}] LLM 返回空结构，使用简单划分")
            acts = generate_simple_acts(chapter_count, structure_type)
    except Exception as e:
        error_kind = "schema_invalid" if isinstance(e, LLMResponseContractError) else "调用失败"
        logger.error(f"[{material_id}] 幕/序列生成 {error_kind}: {e}")
        logger.warning(f"[{material_id}] 使用简单划分继续，不中断流程")
        acts = generate_simple_acts(chapter_count, structure_type)

    _save_acts_temp(outline_dir, acts)
    logger.info(f"[{material_id}] 已保存幕/序列划分中间结果")

    return acts, False


def generate_all_beats(
    acts: list,
    normal_chapters: list,
    config: dict,
    outline_dir: Path,
    material_id: str = "",
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[list, int, int]:
    """逐序列生成 beats（含断点续传和容错）。

    Args:
        acts: 幕数据列表
        normal_chapters: 正常章节数据列表
        config: 配置字典
        outline_dir: 大纲目录路径
        material_id: 素材ID
        progress_callback: 进度回调函数 (done, total, desc) -> None

    Returns:
        (beats_data, total_sequences, failed_sequences) 元组：
        - beats_data: 所有节拍数据列表
        - total_sequences: 序列总数
        - failed_sequences: 失败序列数
    """
    model = config["llm"]["model"]
    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    total_sequences = sum(len(act.get("sequences", [])) for act in acts)

    # 加载进度
    progress = _load_outline_progress(outline_dir)
    completed_seqs = progress.get("completed_sequences", [])

    if completed_seqs:
        prev_total = progress.get("total_sequences", 0)
        if prev_total == total_sequences:
            logger.info(f"[{material_id}] 断点续传：已完成 {len(completed_seqs)}/{total_sequences} 个序列")
        else:
            logger.warning(
                f"[{material_id}] acts 结构变化（{prev_total}→{total_sequences}序列），清理临时文件并重置进度"
            )
            _cleanup_outline_temp_files(outline_dir)
            _save_acts_temp(outline_dir, acts)
            completed_seqs = []

    if progress_callback:
        progress_callback(len(completed_seqs), total_sequences, f"逐序列生成 beats（共 {total_sequences} 个）")
    else:
        logger.info(f"[{material_id}] 逐序列生成 beats（共 {total_sequences} 个序列）...")

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
                        "tension": beat.get("tension", 1),
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
                error_kind = "schema_invalid" if isinstance(e, LLMResponseContractError) else "调用失败"
                logger.error(f"[{material_id}] 序列 {seq_global} beats {error_kind}: {e}")
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
                        "tension": beat.get("tension", 1),
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

    return beats_data, total_sequences, failed_sequences


def record_stage_stats(
    runner: PipelineRunner,
    stage_name: str,
    elapsed: float,
    telemetry,
) -> None:
    """记录阶段统计信息。

    Args:
        runner: PipelineRunner 实例
        stage_name: 阶段名称
        elapsed: 耗时（秒）
        telemetry: 当前阶段显式 telemetry collector
    """
    call_details = telemetry.details
    tokens_in = sum(d.get("input_tokens", 0) for d in call_details)
    tokens_out = sum(d.get("output_tokens", 0) for d in call_details)
    runner.record_stage_complete(
        stage_name=stage_name,
        elapsed=elapsed,
        api_calls=1,
        api_errors=0,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
    )


def init_outline_context(material_id: str, provider: str | None = None) -> dict | None:
    """初始化大纲生成上下文。

    Args:
        material_id: 素材ID
        provider: 服务商名称（可选）

    Returns:
        上下文字典，包含 novel_dir, outline_dir, meta, config, chapter_count 等，
        若初始化失败则返回 None
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return None

    config = load_config(provider)
    outline_dir = novel_dir / "outline"
    outline_dir.mkdir(exist_ok=True)

    meta = load_meta(novel_dir)
    chapter_index, success = load_chapter_index(novel_dir, material_id)
    if not success:
        return None

    return {
        "novel_dir": novel_dir,
        "outline_dir": outline_dir,
        "meta": meta,
        "config": config,
        "chapter_count": len(chapter_index),
        "title": meta.get("name", material_id),
    }


def build_chapter_context(novel_dir: Path, config: dict) -> dict:
    """构建章节上下文数据。

    Args:
        novel_dir: 小说目录路径
        config: 配置字典

    Returns:
        上下文字典，包含 normal_chapters, outline_stats, context_text, context_label
    """
    model = config["llm"]["model"]
    chapters_data = load_chapters_data(novel_dir)
    normal_chapters = [ch for ch in chapters_data if not is_special_chapter_type(ch.get("type", "normal"))]
    outline_stats = _extract_outline_stats(normal_chapters) if normal_chapters else {}

    if normal_chapters:
        context_text = build_summary_pool(normal_chapters, config["llm"]["outline_summary_tokens"], model)
        context_label = f"章级摘要池（共 {len(normal_chapters)} 章）"
    else:
        context_text = load_source_text(novel_dir)
        context_label = "原文摘录（前 5000 字）"

    return {
        "normal_chapters": normal_chapters,
        "outline_stats": outline_stats,
        "context_text": context_text,
        "context_label": context_label,
    }


def run_outline_pipeline(
    ctx: dict,
    progress_callback: Callable[[int, int, str], None] | None = None,
    material_id: str = "",
) -> bool:
    """执行完整的大纲生成流程（前提提炼 + 幕序列划分 + Beats生成）。

    Args:
        ctx: 初始化上下文字典
        progress_callback: 进度回调函数
        material_id: 素材ID

    Returns:
        True 表示成功，False 表示失败
    """
    novel_dir = ctx["novel_dir"]
    outline_dir = ctx["outline_dir"]
    meta = ctx["meta"]
    config = ctx["config"]
    chapter_count = ctx["chapter_count"]

    # 构建章节上下文
    chapter_ctx = build_chapter_context(novel_dir, config)

    # 初始化 PipelineRunner
    runner = PipelineRunner(
        name="大纲生成",
        total_stages=OUTLINE_STAGES,
        novel_dir=novel_dir,
        material_id=material_id,
        novel_info={"name": ctx["title"], "chapter_count": chapter_count, "word_count": meta.get("word_count", "?")},
    )

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    # 第一阶段：前提提炼
    wall_start = time.monotonic()
    premise_data = extract_premise(chapter_ctx["context_text"], chapter_ctx["context_label"], config, material_id)
    save_meta_with_premise(novel_dir, meta, premise_data)
    runner.record_stage_complete(
        "前提提炼",
        time.monotonic() - wall_start,
        api_calls=1,
        api_errors=0 if premise_data.get("premise") else 1,
        tokens_in=0,
        tokens_out=0,
    )
    time.sleep(rate_limit)

    # 第二阶段：幕序列划分
    wall_start = time.monotonic()
    acts, from_cache = generate_acts_with_fallback(
        chapter_count, meta, chapter_ctx["context_text"], chapter_ctx["outline_stats"], config, outline_dir, material_id
    )
    stage_name = "幕序列划分(断点续传)" if from_cache else "幕序列划分"
    elapsed = 0.0 if from_cache else time.monotonic() - wall_start
    runner.record_stage_complete(stage_name, elapsed, api_calls=0 if from_cache else 1, api_errors=0, tokens_in=0, tokens_out=0)

    # 第三阶段：Beats 生成
    wall_start = time.monotonic()
    beats_data, total_sequences, failed_sequences = generate_all_beats(
        acts, chapter_ctx["normal_chapters"], config, outline_dir, material_id, progress_callback
    )
    runner.record_stage_complete(
        f"Beats生成({total_sequences}序列)",
        time.monotonic() - wall_start,
        api_calls=total_sequences,
        api_errors=failed_sequences,
        tokens_in=0,
        tokens_out=0,
    )

    # 保存输出文件
    save_outline_files(outline_dir, meta, acts, build_sequences_data(acts, material_id), beats_data, failed_sequences)
    _cleanup_outline_temp_files(outline_dir)

    logger.info(
        f"[{material_id}] 大纲生成完成: {len(acts)}幕, {total_sequences}序列, {len(beats_data)}节拍"
        + (f" ({failed_sequences}序列失败)" if failed_sequences > 0 else "")
    )
    runner.save_history(status="success")
    return True


__all__ = [
    "extract_premise",
    "generate_acts_with_fallback",
    "generate_all_beats",
    "record_stage_stats",
    "init_outline_context",
    "build_chapter_context",
    "run_outline_pipeline",
]
