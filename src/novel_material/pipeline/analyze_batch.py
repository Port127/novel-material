"""批量分析：一次 API 调用分析多个章节。

此模块包含 analyze_chapters_batch 函数，供 analyze.py 入口调用。
依赖 analyze_utils.py 中的辅助函数和常量。
"""
import time
from novel_material.infra.llm import truncate_to_tokens
from novel_material.infra.progress import get_pipeline_logger
from novel_material.pipeline.analyze_utils import (
    _BATCH_JSON_SCHEMA,
    _get_max_chapter_tokens,
)
from novel_material.pipeline.analyze_temperature import (
    _build_dynamic_system_prompt,
    _should_use_thinking_mode,
    _calculate_dynamic_temperature,
)

logger = get_pipeline_logger()


def analyze_chapters_batch(
    batch_info: list[dict],
    lines: list[str],
    config: dict,
    material_id: str = "",
    batch_index: int = 0,
    total_batches: int = 1,
    range_start_ch: int = 1,
    range_end_ch: int = 0,  # 0 表示自动使用 batch_info 中最大章节号
) -> dict[int, dict]:
    """批量分析多个章节，一次 API 调用返回所有结果。

    相比逐章分析，批量处理可以：
    - 减少 API 调用次数（一次调用分析多章）
    - 缩短总处理时间（省去批次间隔等待）

    参数：
        batch_info：要分析的章节信息列表
        lines：原文所有行
        config：LLM 配置
        material_id：素材 ID（用于日志追踪）
        batch_index：当前批次索引 (0-based)
        total_batches：总批次数
        range_start_ch：分析范围的起始章节号（用于计算进度比例）
        range_end_ch：分析范围的结束章节号（0 表示自动推断）

    返回：
        dict：{章节号: 分析结果}，只包含 LLM 成功返回的章节
        缺失的章节需要用 analyze_chapter 单章处理
    """
    from novel_material.infra.llm import call_llm

    model = config["llm"]["model"]
    n = len(batch_info)

    # 构建每章内容，同时统计字符数
    blocks = []
    total_chars = 0
    for ch_info in batch_info:
        text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])
        truncated = truncate_to_tokens(text, _get_max_chapter_tokens(), model=model)
        block_len = len(truncated)
        total_chars += block_len
        blocks.append(
            f"========== 章节号: {ch_info['chapter']} ==========\n标题: {ch_info['title']}\n内容:\n{truncated}"
        )

    avg_chars_per_ch = total_chars // max(n, 1)
    batch_nums = [ch_info["chapter"] for ch_info in batch_info]
    batch_range = f"#{min(batch_nums)}-{max(batch_nums)}"

    # 打印批次输入统计（DEBUG 级别）
    prefix = f"[{material_id}] " if material_id else ""
    logger.debug(f"{prefix}批次{batch_range} 开始: {total_chars} 字符 ×{n}章")

    combined = ("\n\n" + "=" * 30 + "\n\n").join(blocks)

    # 计算进度比例（基于范围内的相对位置）
    min_ch = min(ch_info["chapter"] for ch_info in batch_info)
    # 如果 range_end_ch 为 0，使用 batch_info 中最大章节号
    effective_end_ch = range_end_ch if range_end_ch > 0 else max(ch_info["chapter"] for ch_info in batch_info)
    range_total = effective_end_ch - range_start_ch + 1
    progress_ratio = (min_ch - range_start_ch) / max(range_total, 1) if range_total > 0 else 0.0

    # 使用动态系统提示词
    dynamic_base = _build_dynamic_system_prompt(progress_ratio, batch_index, total_batches, config)
    system_prompt = (
        dynamic_base
        + f"\n\n本次批量分析 {n} 章，返回 JSON 对象必须包含 chapters 数组，"
        f"每个元素对应一章，顺序与输入一致。"
    )

    user_prompt = f"""请批量分析以下 {n} 章内容：

{combined}

返回 JSON（chapters 数组长度必须等于 {n}）：
{_BATCH_JSON_SCHEMA}

【关键警告 - 章节号必须正确】
- chapter 字段必须使用实际的章节号：{batch_nums}
- 绝对禁止返回 1、2、3 这样的"序号"，必须返回真实章节号
- 示例：如果输入是第 171 章，chapter 字段必须是 171，不是 1 或其他数字
- 每个元素的 chapter 必须严格对应输入中的章节号，顺序一致"""

    # 判断是否使用 thinking 模式（后期章节禁用，改用动态温度）
    thinking_budget = _should_use_thinking_mode(progress_ratio, config)
    temperature_override = _calculate_dynamic_temperature(progress_ratio, config)

    # API 调用计时
    api_start = time.monotonic()
    result = call_llm(
        system_prompt,
        user_prompt,
        config,
        max_tokens_override=n * 1500,
        timeout_override=config["llm"].get("analyze_timeout"),
        context=f"{material_id} 批次{batch_range}",
        thinking_budget=thinking_budget,
        temperature_override=temperature_override,
    )
    api_elapsed = time.monotonic() - api_start

    # 解析计时
    parse_start = time.monotonic()

    # 解析返回结果：兼容 LLM 直接返回数组的情况
    if isinstance(result, list):
        logger.warning(f"{prefix}批量返回为裸数组（非 {{'chapters': [...]}} 格式），自动适配")
        chapters_list = result
    else:
        chapters_list = result.get("chapters", [])
        if not chapters_list:
            logger.warning(f"{prefix}批量返回无 chapters 数组，实际返回键: {list(result.keys())}")
            # 兼容：如果返回单个章节对象而非数组
            if result.get("summary") and batch_info:
                logger.warning(f"{prefix}检测到单章格式返回，尝试兼容解析")
                return {batch_info[0]["chapter"]: result}

    parsed = {}
    for item in chapters_list:
        if isinstance(item, dict) and isinstance(item.get("chapter"), int):
            parsed[item["chapter"]] = item
        else:
            logger.warning(f"{prefix}跳过无效章节项: {item}")

    if len(parsed) < len(chapters_list):
        logger.warning(f"{prefix}解析丢失 {len(chapters_list) - len(parsed)} 章")

    # 批次解析质量统计：验证章节号是否与期望一致
    expected_chapters = set(ch["chapter"] for ch in batch_info)
    returned_chapters = set(parsed.keys())
    missing = sorted(expected_chapters - returned_chapters)
    extra = sorted(returned_chapters - expected_chapters)  # LLM 返回了不在批次中的章节号

    returned_count = len(parsed)
    missing_count = len(missing)

    parse_elapsed = time.monotonic() - parse_start

    if missing_count > 0:
        logger.warning(
            f"{prefix}批次{batch_range} 章节号错位: 期望 {sorted(expected_chapters)}，"
            f"实际 {sorted(returned_chapters)}，缺失 {missing}"
        )

    if extra:
        logger.warning(
            f"{prefix}批次{batch_range} 章节号错位: 返回了非期望章节号 {extra}（期望 {sorted(expected_chapters)}）"
        )

    # 每章输出统计
    total_summary_chars = sum(len(ch.get("summary", "")) for ch in parsed.values())
    avg_summary_len = total_summary_chars // max(returned_count, 1)
    tension_values = []
    for ch_data in parsed.values():
        tension = ch_data.get("tension_level", 0)
        if tension:
            tension_values.append(tension)

    # 输出批次质量摘要
    tension_range = f"{min(tension_values)}-{max(tension_values)}" if tension_values else "?"
    logger.info(
        f"{prefix}批次{batch_range} 完成: 返回 {returned_count}/{n} 章 | "
        f"摘要={avg_summary_len}字 | 张力={tension_range} | "
        f"API {api_elapsed:.1f}s | 解析 {parse_elapsed:.2f}s"
    )

    return parsed