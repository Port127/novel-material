"""总体评估：对小说做全局评估，生成类型、主线概要、阶段概要、核心人物提示。

工作流程：
1. 加载章节索引和原文
2. 选取样本章节（小体量15章/大体量50章）
3. 分5批次调用 LLM 评估，渐进式积累阶段概要
4. 输出 evaluation.yaml

特性：
- 断点续传：使用 _evaluation_progress.yaml 记录进度
- 样本策略：复用 loader.py 的分层采样逻辑
"""
import sys
import time
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml, save_yaml, load_yaml_list
from novel_material.infra.llm import load_config, call_llm, truncate_to_tokens, start_llm_telemetry
from novel_material.infra.progress import StageTracker, save_run_history, get_pipeline_logger
from novel_material.infra.llm_contracts import LLMResponseContractError, require_mapping, require_string, require_string_list
from novel_material.pipeline.progress import EVALUATION_STAGES
from novel_material.infra.common import NOVEL_TYPE_VALUES
from novel_material.schema import get_threshold

logger = get_pipeline_logger()


def normalize_evaluation_response(payload: object) -> dict:
    result = dict(require_mapping(payload, "evaluation"))
    result["novel_type"] = require_string_list(result.get("novel_type"), "evaluation.novel_type")
    result["main_thread_summary"] = require_string(result.get("main_thread_summary"), "evaluation.main_thread_summary")
    result["core_characters_hint"] = require_string_list(result.get("core_characters_hint"), "evaluation.core_characters_hint")
    result["stage_summary"] = require_string(result.get("stage_summary"), "evaluation.stage_summary")
    return result

# 章节数阈值：超过此数量启用大样本策略（从契约加载）
_SAMPLE_THRESHOLD = get_threshold("sample_threshold")


def _get_available_genres() -> list[str]:
    """获取可用的小说类型列表。

    优先从数据库加载 genre_domain_map，失败则使用 constants 中的 fallback。
    """
    try:
        from novel_material.tags.load import get_all_genres
        genres = get_all_genres()
        if genres:
            return genres
    except Exception:
        pass  # 数据库未连接或其他错误，使用 fallback

    return NOVEL_TYPE_VALUES


def _get_max_sample_tokens() -> int:
    """读取单批次样本输入截断上限。"""
    try:
        from novel_material.infra.config import get_settings
        return int(get_settings().get("LLM_EVALUATION_SAMPLE_TOKENS", 8000))
    except (TypeError, ValueError):
        return 8000


_SYSTEM_PROMPT = """你是专业的小说全局分析助手，负责评估小说的整体结构和类型。

任务：
1. novel_type：从给定类型列表中选取最匹配的1-3个
2. main_thread_summary：主线情节的200-300字概要
3. core_characters_hint：核心人物名单（3-5个关键角色，仅写名字）
4. stage_summary：当前样本覆盖阶段的100字概要

注意：
- 你只分析样本章节，不需要完整全书内容
- stage_summary 应描述当前样本覆盖的故事阶段（开篇/发展/高潮/转折/收尾）
- 如果已有前批次的阶段概要，请在此基础上补充新阶段"""


# JSON 返回格式示例
_EVALUATION_JSON_SCHEMA = """{
  "novel_type": ["类型1", "类型2"],
  "main_thread_summary": "主线情节概要，200-300字...",
  "core_characters_hint": ["人物1", "人物2", "人物3"],
  "stage_summary": "当前阶段概要，100字..."
}"""


def select_evaluation_samples(chapter_index: list[dict], total_chapters: int) -> dict[int, list[dict]]:
    """选取评估样本，返回 {批次号: 样本章节列表}。

    算法：
    - 小体量（<200章）：15章分5批，每批3章
    - 大体量（≥200章）：50章分5批，每批10章

    采样策略：
    - 固定包含首章（第1章）和尾章（最后一章）
    - 中间章节按比例均匀分布
    - 5批次渐进式覆盖全书范围
    """
    is_large = total_chapters >= _SAMPLE_THRESHOLD
    total_samples = 50 if is_large else 15
    batch_size = 10 if is_large else 3

    # 构建采样索引：确保首尾都被包含
    sampled_indices: list[int] = []

    if total_samples >= 2:
        # 首章（固定）
        sampled_indices.append(0)

        # 中间章节：均匀分布
        if total_samples > 2:
            step = (total_chapters - 1) / (total_samples - 1)
            for i in range(1, total_samples - 1):
                sampled_indices.append(int(i * step))

        # 尾章（固定）
        sampled_indices.append(total_chapters - 1)

    # 按5批次分配样本
    batches: dict[int, list[dict]] = {}
    for batch_num in range(1, 6):
        start_idx = (batch_num - 1) * batch_size
        end_idx = min(start_idx + batch_size, len(sampled_indices))

        batch_indices = sampled_indices[start_idx:end_idx]
        batch_chapters = [chapter_index[i] for i in batch_indices if i < total_chapters]
        batches[batch_num] = batch_chapters

    return batches


def load_evaluation_progress(material_id: str) -> dict:
    """加载评估进度文件，用于断点续传。

    返回：
        dict: 包含 completed_batches、stage_summaries 等字段
    """
    novel_dir = NOVELS_DIR / material_id
    progress_file = novel_dir / "_evaluation_progress.yaml"

    if not progress_file.exists():
        return {
            "completed_batches": [],
            "stage_summaries": {},
            "novel_type": [],
            "main_thread_summary": "",
            "core_characters_hint": [],
        }

    return load_yaml(progress_file)


def save_evaluation_progress(material_id: str, progress: dict) -> None:
    """保存评估进度。"""
    novel_dir = NOVELS_DIR / material_id
    progress_file = novel_dir / "_evaluation_progress.yaml"
    progress["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    save_yaml(progress_file, progress)


def load_evaluation(material_id: str) -> dict | None:
    """加载总体评估结果。

    用于滑动窗口模式，为章级分析提供全局上下文。

    返回：
        dict | None：评估结果，如果不存在则返回 None
    """
    eval_file = NOVELS_DIR / material_id / "evaluation.yaml"
    if not eval_file.exists():
        return None
    return load_yaml(eval_file)


def _build_sample_text(sample_chapters: list[dict], lines: list[str], max_tokens: int, model: str) -> str:
    """构建样本章节文本。"""
    blocks = []
    for ch_info in sample_chapters:
        text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])
        truncated = truncate_to_tokens(text, max_tokens // len(sample_chapters), model=model)
        blocks.append(
            f"========== 章节号: {ch_info['chapter']} ==========\n标题: {ch_info['title']}\n内容:\n{truncated}"
        )
    return ("\n\n" + "=" * 30 + "\n\n").join(blocks)


def evaluate_batch(
    batch_num: int,
    sample_chapters: list[dict],
    lines: list[str],
    previous_progress: dict,
    available_genres: list[str],
    config: dict,
    material_id: str,
    tracker: StageTracker,
) -> dict:
    """评估单个批次的样本章节。

    参数：
        batch_num: 批次号（1-5）
        sample_chapters: 样本章节信息列表
        lines: 原文行列表
        previous_progress: 前批次的进度（包含 stage_summaries）
        available_genres: 可用的小说类型列表
        config: LLM 配置
        material_id: 素材 ID
        tracker: 进度跟踪器

    返回：
        dict: 包含 novel_type、main_thread_summary、core_characters_hint、stage_summary
    """
    model = config["llm"]["model"]
    max_tokens = _get_max_sample_tokens()

    # 构建样本文本
    sample_text = _build_sample_text(sample_chapters, lines, max_tokens, model)

    # 构建前批次概要提示
    previous_stages = previous_progress.get("stage_summaries", {})
    previous_stages_text = ""
    if previous_stages:
        previous_stages_text = "已完成的阶段概要：\n"
        for stage_num, summary in sorted(previous_stages.items()):
            previous_stages_text += f"阶段{stage_num}: {summary}\n"
        previous_stages_text += "\n请在此基础上补充新阶段的概要。"

    # 已有的主线概要和人物提示
    previous_main_thread = previous_progress.get("main_thread_summary", "")
    previous_characters = previous_progress.get("core_characters_hint", [])

    # 类型列表提示
    genres_list_str = ", ".join(available_genres)

    user_prompt = f"""请分析以下样本章节（批次 {batch_num}/5）：

{sample_text}

{previous_stages_text}

已有信息：
- 主线概要：{previous_main_thread or "（尚未生成）"}
- 核心人物：{', '.join(previous_characters) if previous_characters else "（尚未识别）"}

可用小说类型列表：{genres_list_str}

请返回 JSON：
{_EVALUATION_JSON_SCHEMA}

要求：
1. novel_type：从上述类型列表中选取1-3个最匹配的类型
2. main_thread_summary：如果有已有概要，请在此基础上补充完善（200-300字）
3. core_characters_hint：如果有已有人物，请在此基础上补充（3-5个关键人物）
4. stage_summary：描述当前批次样本覆盖的故事阶段（开篇/发展/高潮/转折/收尾，100字左右）"""

    # 调用 LLM
    tracker.start_spinner(f"批次{batch_num}评估")
    telemetry = start_llm_telemetry()

    try:
        result = normalize_evaluation_response(call_llm(
            _SYSTEM_PROMPT,
            user_prompt,
            config,
            max_tokens_override=1500,
            timeout_override=config["llm"].get("other_timeout", 120),
            context=f"{material_id} 批次#{batch_num}",
        ))
        tracker.record_api_call(success=True)

        # 记录 tokens
        in_tokens = telemetry.last.get("input_tokens", 0)
        out_tokens = telemetry.last.get("output_tokens", 0)
        tracker.record_tokens(in_tokens, out_tokens)

    except Exception as e:
        tracker.record_api_call(success=False)
        tracker.stop_spinner()
        raise e

    tracker.stop_spinner()

    # 解析结果
    novel_type = result.get("novel_type", [])
    main_thread_summary = result.get("main_thread_summary", "")
    core_characters_hint = result.get("core_characters_hint", [])
    stage_summary = result.get("stage_summary", "")

    # 合并结果（保留前批次的积累）
    merged_novel_type = list(set(previous_progress.get("novel_type", []) + novel_type))
    merged_main_thread = main_thread_summary if len(main_thread_summary) > len(previous_main_thread) else previous_main_thread
    merged_characters = list(set(previous_characters + core_characters_hint))

    return {
        "novel_type": merged_novel_type[:3],  # 最多3个类型
        "main_thread_summary": merged_main_thread,
        "core_characters_hint": merged_characters[:10],  # 最多10个人物
        "stage_summary": stage_summary,
        "_finish_reason": telemetry.last.get("finish_reason", ""),
    }


def run_evaluation(
    material_id: str,
    provider: str | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    silent: bool = False,
) -> bool:
    """执行总体评估流程。

    流程：
    1. 加载章节索引和原文
    2. 检查评估进度（断点续传）
    3. 选取样本章节
    4. 分5批次调用 LLM 评估
    5. 合并结果并写入 evaluation.yaml

    参数：
        material_id：素材 ID
        provider：LLM 服务商名称（可选）
        progress_callback：进度回调函数
        silent：禁止内部打印（用于 Rich Progress 上下文）

    返回：
        True 表示成功，False 表示失败
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    config = load_config(provider)

    # 加载小说基本信息
    meta_file = novel_dir / "meta.yaml"
    meta = {}
    if meta_file.exists():
        meta = load_yaml(meta_file)

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "raw")

    # 加载章节索引（检查文件存在性）
    chapter_index_file = novel_dir / "chapter_index.yaml"
    if not chapter_index_file.exists():
        logger.error(f"[{material_id}] chapter_index.yaml 不存在，请先执行入库")
        return False
    chapter_index = load_yaml_list(chapter_index_file)

    if not chapter_index:
        logger.error(f"[{material_id}] chapter_index.yaml 为空")
        return False

    total_chapters = len(chapter_index)
    logger.info(f"[{material_id}] 小说: {title} | {total_chapters} 章 | {word_count} 字 | 状态: {status}")

    # 加载原文（检查文件存在性）
    source_file = novel_dir / "source.txt"
    if not source_file.exists():
        logger.error(f"[{material_id}] source.txt 不存在，请先执行入库")
        return False
    with open(source_file, "r", encoding="utf-8") as f:
        full_text = f.read()
    lines = full_text.split("\n")

    # 选取样本
    batches = select_evaluation_samples(chapter_index, total_chapters)

    # 获取可用的小说类型列表
    available_genres = _get_available_genres()
    logger.debug(f"[{material_id}] 可用类型列表: {available_genres}")

    # 加载评估进度（断点续传）
    progress = load_evaluation_progress(material_id)
    completed_batches = set(progress.get("completed_batches", []))

    pending_batches = [b for b in range(1, 6) if b not in completed_batches]

    if not pending_batches:
        logger.info(f"[{material_id}] 评估已完成，跳过")
        return True

    logger.info(f"[{material_id}] 待评估: 批次 {pending_batches}")

    # 使用 StageTracker 进行进度跟踪
    tracker = StageTracker(
        total_stages=EVALUATION_STAGES,
        stage_name="总体评估",
        material_id=material_id,
        novel_info={"name": title, "chapter_count": total_chapters, "word_count": word_count},
        silent=silent,
    )
    tracker.print_header()

    total_elapsed = 0
    stage_times = []

    for batch_num in pending_batches:
        sample_chapters = batches.get(batch_num, [])
        if not sample_chapters:
            logger.warning(f"[{material_id}] 批次#{batch_num} 无样本章节")
            continue

        batch_start = time.monotonic()
        # 记录 token 基准值（用于计算增量）
        tokens_base_in = tracker._tokens_in
        tokens_base_out = tracker._tokens_out

        try:
            result = evaluate_batch(
                batch_num,
                sample_chapters,
                lines,
                progress,
                available_genres,
                config,
                material_id,
                tracker,
            )
        except Exception as e:
            error_kind = "schema_invalid" if isinstance(e, LLMResponseContractError) else "调用失败"
            logger.error(f"[{material_id}] 批次#{batch_num} 评估 {error_kind}: {e}")
            tracker.stop_spinner()
            return False

        batch_elapsed = time.monotonic() - batch_start
        total_elapsed += batch_elapsed
        # 记录增量 token（而非累计值）
        stage_times.append({
            "name": f"批次{batch_num}",
            "elapsed_sec": batch_elapsed,
            "api_calls": 1,
            "api_errors": 0,
            "tokens_in": tracker._tokens_in - tokens_base_in,
            "tokens_out": tracker._tokens_out - tokens_base_out,
        })

        # 更新进度
        # 注意：batch_num 与 stage_num 数值对应（批次1→开篇阶段，批次2→发展阶段...）
        # 但语义不同：batch_num 是采样批次序号，stage_num 是故事阶段序号
        progress["completed_batches"] = list(completed_batches | {batch_num})
        progress["stage_summaries"][batch_num] = result.get("stage_summary", "")
        progress["novel_type"] = result.get("novel_type", [])
        progress["main_thread_summary"] = result.get("main_thread_summary", "")
        progress["core_characters_hint"] = result.get("core_characters_hint", [])
        completed_batches.add(batch_num)

        # 保存进度（断点续传）
        save_evaluation_progress(material_id, progress)

        finish_reason = result.pop("_finish_reason", "")
        logger.info(
            f"[{material_id}] 批次#{batch_num} 完成: {batch_elapsed:.1f}s | "
            f"tokens {tracker._tokens_in}/{tracker._tokens_out} | finish={finish_reason}"
        )

        if progress_callback:
            progress_callback(len(completed_batches), 5, f"批次#{batch_num}完成")

        # 批次间等待（避免速率限制）
        rate_limit = config["llm"].get("rate_limit_seconds", 1)
        if batch_num < 5:
            time.sleep(rate_limit)

    tracker.print_footer()

    # 生成最终 evaluation.yaml
    evaluation = {
        "schema_version": "2.0.1",
        "novel_type": progress.get("novel_type", []),
        "main_thread_summary": progress.get("main_thread_summary", ""),
        "total_chapters": total_chapters,
        "core_characters_hint": progress.get("core_characters_hint", []),
        "stage_summaries": {
            i: progress.get("stage_summaries", {}).get(i, "")
            for i in range(1, 6)
        },
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    evaluation_file = novel_dir / "evaluation.yaml"

    save_yaml(evaluation_file, evaluation)

    logger.info(f"[{material_id}] 评估完成，已写入: {evaluation_file}")

    # 删除进度文件
    progress_file = novel_dir / "_evaluation_progress.yaml"
    if progress_file.exists():
        progress_file.unlink()

    # 更新状态为 evaluated
    from novel_material.infra.config import update_meta_status
    update_meta_status(material_id, "evaluated")

    # 保存运行历史
    save_run_history(
        novel_dir=novel_dir,
        pipeline_name="总体评估",
        stage_times=stage_times,
        total_elapsed=total_elapsed,
        status="success",
    )

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python evaluate.py <material_id>")
        sys.exit(1)

    success = run_evaluation(sys.argv[1])
    sys.exit(0 if success else 1)
