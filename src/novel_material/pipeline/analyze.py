"""章节分析：为每章生成摘要、出场人物、功能标签等结构化数据。

工作流程：
1. 读取 chapter_index.yaml（章节索引）和 source.txt（原文）
2. 调用 LLM 分析每章内容，生成：
   - summary：50-100 字摘要
   - characters_appear：出场人物列表
   - chapter_functions：章节功能标签
   - tension_level：紧张程度（1-5）
3. 结果写入 chapters/{章节号}.yaml（每章独立文件）
4. 完成后合并为 chapters.yaml（完整快照）

特性：
- 断点续传：已分析的章节自动跳过，从中断处继续
- 批量处理：可一次分析多章，减少 API 调用次数
- Token 截断：每章内容限制在 LLM_MAX_CHAPTER_TOKENS 内（settings.yaml 默认 5000）
- 滑动窗口（可选）：启用时提供前后章上下文，输出张力变化、情感过渡、情节进度
"""
import sys
import yaml
import time
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR, update_meta_status, get_settings
from novel_material.infra.llm import load_config, call_llm, truncate_to_tokens, get_last_call_finish_reason
from novel_material.validation.quality import run_quality_check, get_short_summary_chapters
from novel_material.validation.pacing_normalize import normalize_pacing
from novel_material.infra.progress import get_pipeline_logger
from novel_material.infra.constants import TENSION_CHANGE_VALUES
from novel_material.validation.schema import validate_chapter_tags_fields
from novel_material.pipeline.evaluate import load_evaluation

logger = get_pipeline_logger()


def _fmt_duration(sec: float) -> str:
    """将秒数格式化为可读时长（用于 ETA 显示）。"""
    if sec < 60:
        return f"{sec:.0f}s"
    elif sec < 3600:
        return f"{sec / 60:.0f}min"
    else:
        h = int(sec // 3600)
        m = int((sec % 3600) / 60)
        return f"{h}h{m}min"


def _get_max_chapter_tokens() -> int:
    """读取单章输入截断上限配置。"""
    try:
        return int(get_settings().get("LLM_MAX_CHAPTER_TOKENS", 5000))
    except (TypeError, ValueError):
        return 5000

_SYSTEM_PROMPT = """你是专业的小说分析助手，负责对每章内容生成摘要和分析。

返回 JSON 必须包含以下所有字段：
1. summary：章节摘要，50-100字
2. characters_appear：出场人物列表（仅写名字）
3. chapter_functions：章节功能标签（从字典选取）
4. tension_level：紧张程度，1-5
5. pacing：节奏，可选值：快/中/慢/喘息/加速
6. setting：场景列表
7. key_event：关键事件精炼描述，10-30字
8. emotional_tone：情感基调标签数组（必填），如 ["压抑", "紧张", "燃"]
9. scene_type：场景类型标签数组（必填），如 ["战斗", "突破", "告别"]
10. technique：叙事技巧标签数组（必填），如 ["闪回", "独白"]，若无特殊技巧填 []
11. hook_type：章末钩子类型（必填），可选：悬念钩子/反转钩子/情感钩子/信息钩子/危机钩子/无钩子

滑动窗口字段（仅当提供了前章上下文时）：
- tension_change：张力变化方向（上升/持平/下降）
- emotion_transition：情感过渡描述（10-50字）
- plot_progress：情节进度描述（20-100字）"""


def _build_dynamic_system_prompt(
    progress_ratio: float,
    batch_index: int,
    total_batches: int,
    config: dict,
) -> str:
    """构建动态系统提示词，根据进度位置注入多样性提醒。

    参数：
        progress_ratio: 当前进度比例 (0.0-1.0)
        batch_index: 当前批次索引 (0-based)
        total_batches: 总批次数
        config: LLM 配置

    返回：
        动态生成的系统提示词
    """
    dynamic_enabled = config["llm"].get("dynamic_prompt_enabled", True)
    if not dynamic_enabled:
        return _SYSTEM_PROMPT

    base_prompt = _SYSTEM_PROMPT

    # 进度阶段描述
    progress_desc = ""
    if progress_ratio < 0.2:
        progress_desc = "\n【当前分析：开篇部分】请关注故事建立、人物登场、世界观铺垫。"
    elif progress_ratio < 0.5:
        progress_desc = "\n【当前分析：发展部分】请关注情节推进、冲突演变、人物成长。"
    elif progress_ratio < 0.8:
        progress_desc = "\n【当前分析：高潮部分】请关注张力峰值、关键转折、情感爆发。"
    else:
        progress_desc = "\n【当前分析：收尾部分】请关注结局走向、伏笔回收、人物命运。"

    # 多样性唤醒：每隔 N 批次插入提醒
    diversity_reminder = ""
    interval = config["llm"].get("diversity_reminder_interval", 10)
    if batch_index > 0 and batch_index % interval == 0:
        diversity_reminder = f"""
【独立性提醒 - 第{batch_index + 1}批次】
- 本批次章节与之前已分析的章节是独立的故事片段，请重新聚焦
- 摘要应突出本批次章节的独特事件，避免使用通用模板描述
- 每章的 tension_level 应根据该章实际内容独立评估，不要因进度位置而预设
- 出场人物识别需重新审视，不要仅依赖已建立的人物列表"""

    # 后期章节特别提醒（防止"敷衍"趋势）
    late_warning = ""
    threshold = config["llm"].get("late_chapter_threshold", 0.6)
    if progress_ratio > threshold:
        late_warning = """
【后期分析特别要求】
- 后期章节同样需要详细分析，不要因接近结尾而简化输出
- 每章摘要必须包含具体事件，禁用"继续推进剧情"等泛泛描述
- tension_level 应反映该章真实张力，后期章节张力可能波动而非单调下降"""

    return base_prompt + progress_desc + diversity_reminder + late_warning


def _should_use_thinking_mode(
    progress_ratio: float,
    config: dict
) -> int | None:
    """判断是否使用 thinking 模式。

    策略：前期章节使用 thinking 模式提升分析质量，
    后期章节禁用 thinking 改用动态温度增加多样性。

    参数：
        progress_ratio: 当前进度比例
        config: LLM 配置

    返回：
        thinking_budget 值（前期），或 None（后期禁用）
    """
    threshold = config["llm"].get("late_chapter_threshold", 0.6)
    dynamic_temp_enabled = config["llm"].get("dynamic_temperature_enabled", True)

    # 后期章节：如果启用动态温度，禁用 thinking 以让 temperature 生效
    if progress_ratio > threshold and dynamic_temp_enabled:
        return None

    # 前期章节：使用 thinking 模式
    return 12000


def _calculate_dynamic_temperature(
    progress_ratio: float,
    config: dict
) -> float | None:
    """计算动态温度（后期章节适当提高）。

    参数：
        progress_ratio: 当前进度比例
        config: LLM 配置

    返回：
        调整后的温度值，若不需要调整则返回 None
    """
    dynamic_enabled = config["llm"].get("dynamic_temperature_enabled", True)
    if not dynamic_enabled:
        return None

    threshold = config["llm"].get("late_chapter_threshold", 0.6)
    if progress_ratio <= threshold:
        return None

    boost = config["llm"].get("late_temperature_boost", 0.15)
    base_temp = config["llm"].get("temperature", 0.3)
    temp_max = config["llm"].get("temperature_max", 0.6)

    adjusted = base_temp + boost
    return min(adjusted, temp_max)


# LLM 返回格式的示例（单章）
_CHAPTER_JSON_SCHEMA = """{
  "chapter": 1,
  "summary": "章节摘要，50-100字",
  "characters_appear": ["人物名1", "人物名2"],
  "chapter_functions": ["日常", "战斗"],
  "tension_level": 3,
  "pacing": "快",
  "setting": ["室内", "学校"],
  "key_event": "本章关键事件，10-30字精炼描述",
  "emotional_tone": ["压抑", "紧张"],
  "scene_type": ["战斗", "突破"],
  "technique": ["闪回", "独白"],
  "hook_type": "悬念钩子"
}"""

# LLM 返回格式的示例（单章，滑动窗口模式）
_CHAPTER_JSON_SCHEMA_WITH_WINDOW = """{
  "chapter": 1,
  "summary": "章节摘要，50-100字",
  "characters_appear": ["人物名1", "人物名2"],
  "chapter_functions": ["日常", "战斗"],
  "tension_level": 3,
  "pacing": "快",
  "setting": ["室内", "学校"],
  "key_event": "本章关键事件，10-30字精炼描述",
  "tension_change": "上升",
  "emotion_transition": "紧张→释然",
  "plot_progress": "推进主线，揭示新线索",
  "emotional_tone": ["压抑", "紧张"],
  "scene_type": ["战斗", "突破"],
  "technique": ["闪回", "独白"],
  "hook_type": "悬念钩子"
}"""

# LLM 返回格式的示例（批量）
# 注意：示例中用占位符，避免 LLM 误解为序号
_BATCH_JSON_SCHEMA = """{
  "chapters": [
    {"chapter": 章节号, "summary": "摘要内容", "characters_appear": ["人物名"],
     "chapter_functions": ["标签"], "tension_level": 3, "pacing": "快",
     "setting": ["场景"], "key_event": "关键事件描述",
     "emotional_tone": ["压抑"], "scene_type": ["战斗"],
     "technique": ["闪回"], "hook_type": "悬念钩子"}
  ]
}

关键：chapter 字段必须是输入中的实际章节号（如 171、172），绝对不能用序号（如 1、2、3）"""


def build_sliding_window_context(
    chapter_num: int,
    chapters_data: dict[int, dict],
    lines: list[str],
    chapter_index: list[dict],
    evaluation: dict | None,
    next_preview_chars: int = 500,
) -> dict:
    """构建滑动窗口上下文。

    参数：
        chapter_num：当前章节号
        chapters_data：已分析的章节数据 {章节号: 数据}
        lines：原文行列表
        chapter_index：章节索引列表
        evaluation：总体评估结果（可选）
        next_preview_chars：下章预览字符数（默认500）

    返回：
        dict：{
            "evaluation_summary": "全局评估摘要",
            "prev_chapter_summary": "前章摘要（None 表示第一章）",
            "prev_tension_level": 前章张力值,
            "current_chapter_text": "当前章原文",
            "next_chapter_preview": "下章前N字（None 表示最后一章）"
        }
    """
    # 构建全局评估摘要（100字提炼）
    eval_summary = ""
    if evaluation:
        novel_type = evaluation.get("novel_type", [])
        main_thread = evaluation.get("main_thread_summary", "")
        core_chars = evaluation.get("core_characters_hint", [])
        eval_summary = f"类型：{', '.join(novel_type)}\n主线：{main_thread[:100]}...\n核心人物：{', '.join(core_chars[:5])}"

    # 前章摘要和张力
    prev_summary = None
    prev_tension = None
    if chapter_num > 1:
        prev_ch = chapters_data.get(chapter_num - 1)
        if prev_ch:
            prev_summary = prev_ch.get("summary", "")
            prev_tension = prev_ch.get("tension_level", 0)

    # 当前章原文（从 chapter_index 获取行范围）
    current_text = ""
    for ch_info in chapter_index:
        if ch_info.get("chapter") == chapter_num:
            start_line = ch_info.get("start_line", 1)
            end_line = ch_info.get("end_line", len(lines))
            current_text = "\n".join(lines[start_line - 1:end_line])
            break

    # 下章预览（前N字）
    next_preview = None
    for ch_info in chapter_index:
        if ch_info.get("chapter") == chapter_num + 1:
            start_line = ch_info.get("start_line", 1)
            end_line = ch_info.get("end_line", len(lines))
            next_text = "\n".join(lines[start_line - 1:end_line])
            next_preview = next_text[:next_preview_chars]
            break

    return {
        "evaluation_summary": eval_summary,
        "prev_chapter_summary": prev_summary,
        "prev_tension_level": prev_tension,
        "current_chapter_text": current_text,
        "next_chapter_preview": next_preview,
    }


def validate_window_fields(result: dict, prev_tension: int | None) -> list[str]:
    """校验滑动窗口新增字段，返回错误列表。

    参数：
        result：LLM 返回结果
        prev_tension：前章张力值（用于校验 tension_change）

    返回：
        list[str]：错误描述列表
    """
    errors = []

    # tension_change 校验
    tension_change = result.get("tension_change")
    if tension_change:
        if tension_change not in TENSION_CHANGE_VALUES:
            errors.append(f"tension_change 值 '{tension_change}' 不合法")

        # 检查与前章张力的一致性（如果有）
        if prev_tension is not None:
            current_tension = result.get("tension_level", 0)
            if current_tension:
                expected_change = None
                if current_tension > prev_tension:
                    expected_change = "上升"
                elif current_tension < prev_tension:
                    expected_change = "下降"
                else:
                    expected_change = "持平"

                if tension_change != expected_change:
                    errors.append(
                        f"tension_change '{tension_change}' 与张力变化不一致 "
                        f"(前章{prev_tension}→当前{current_tension}，期望'{expected_change}')"
                    )

    # emotion_transition 校验
    emotion = result.get("emotion_transition")
    if emotion and len(emotion) < 5:
        errors.append(f"emotion_transition 过短 ({len(emotion)}字)")

    # plot_progress 校验
    progress = result.get("plot_progress")
    if progress and len(progress) < 10:
        errors.append(f"plot_progress 过短 ({len(progress)}字)")

    return errors


def analyze_chapter(
    content: str,
    chapter_info: dict,
    config: dict,
    progress_ratio: float = 0.0,
    material_id: str = "",
    window_context: dict | None = None,
) -> dict:
    """分析单个章节，返回结构化数据。

    参数：
        content：章节原文
        chapter_info：章节信息（章节号、标题）
        config：LLM 配置
        progress_ratio：进度比例（用于动态提示词和温度策略）
        material_id：素材 ID（用于日志追踪）
        window_context：滑动窗口上下文（可选），包含前章摘要、全局评估等

    返回：
        dict：包含 summary、characters_appear、tension_level 等字段
    """
    model = config["llm"]["model"]
    # 截断过长的章节内容
    truncated = truncate_to_tokens(content, _get_max_chapter_tokens(), model=model)

    # 使用动态系统提示词
    dynamic_prompt_enabled = config["llm"].get("dynamic_prompt_enabled", True)
    if dynamic_prompt_enabled:
        system_prompt = _build_dynamic_system_prompt(progress_ratio, 0, 1, config)
    else:
        system_prompt = _SYSTEM_PROMPT

    # 构建用户提示词
    if window_context:
        # 滑动窗口模式：注入上下文
        eval_summary = window_context.get("evaluation_summary", "")
        prev_summary = window_context.get("prev_chapter_summary")
        prev_tension = window_context.get("prev_tension_level")
        next_preview = window_context.get("next_chapter_preview")

        context_parts = []
        if eval_summary:
            context_parts.append(f"全局评估：\n{eval_summary}")
        if prev_summary:
            context_parts.append(f"前章摘要（张力={prev_tension}）：\n{prev_summary}")
        else:
            context_parts.append("前章摘要：（第一章，无前章）")
        if next_preview:
            context_parts.append(f"下章预览（前500字）：\n{next_preview}")
        else:
            context_parts.append("下章预览：（最后一章，无下章）")

        user_prompt = f"""{chr(10).join(context_parts)}

当前章节：
章节号：{chapter_info.get('chapter', 'N/A')}
标题：{chapter_info.get('title', 'N/A')}
内容：
{truncated}

请分析当前章节，返回 JSON 格式：
{_CHAPTER_JSON_SCHEMA_WITH_WINDOW}"""
    else:
        # 普通模式
        user_prompt = f"""请分析以下章节：

章节号：{chapter_info.get('chapter', 'N/A')}
标题：{chapter_info.get('title', 'N/A')}

内容：
{truncated}

请返回 JSON 格式：
{_CHAPTER_JSON_SCHEMA}"""

    # 动态温度和 thinking 模式
    thinking_budget = _should_use_thinking_mode(progress_ratio, config)
    temperature_override = _calculate_dynamic_temperature(progress_ratio, config)

    timeout = config["llm"].get("analyze_timeout", 300)
    context = f"{material_id} 单章#{chapter_info.get('chapter', 'N/A')}"
    return call_llm(
        system_prompt, user_prompt, config,
        timeout_override=timeout, context=context,
        thinking_budget=thinking_budget,
        temperature_override=temperature_override,
    )


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
    batch_range = f"{min(batch_nums)}-{max(batch_nums)}"

    # 打印批次输入统计（DEBUG 级别）
    prefix = f"[{material_id}] " if material_id else ""
    logger.debug(f"{prefix}批次[{batch_range}] 开始: {total_chars} 字符 ×{n}章")

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
        context=f"{material_id} 批次[{batch_range}]",
        thinking_budget=thinking_budget,
        temperature_override=temperature_override,
    )
    api_elapsed = time.monotonic() - api_start

    # 解析计时
    parse_start = time.monotonic()

    # 解析返回结果：兼容 LLM 直接返回数组的情况
    if isinstance(result, list):
        logger.warning(f"{prefix}批量返回为裸数组（非 {'chapters': [...]} 格式），自动适配")
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
            f"{prefix}批次[{batch_range}] 章节号错位: 期望 {sorted(expected_chapters)}，"
            f"实际 {sorted(returned_chapters)}，缺失 {missing}"
        )

    if extra:
        logger.warning(
            f"{prefix}批次[{batch_range}] 章节号错位: 返回了非期望章节号 {extra}（期望 {sorted(expected_chapters)}）"
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
        f"{prefix}批次[{batch_range}] 完成: 返回 {returned_count}/{n} 章 | "
        f"摘要={avg_summary_len}字 | 张力={tension_range} | "
        f"API {api_elapsed:.1f}s | 解析 {parse_elapsed:.2f}s"
    )

    return parsed


def validate_chapter_analysis(result: dict, chapter_info: dict) -> list[str]:
    """检查分析结果是否合格，返回问题列表。

    检查项：
    - 摘要长度是否足够
    - tension_level 是否在有效范围内
    - 是否识别到出场人物

    特殊类型章节（afterword/author_note）放宽检查。
    """
    errors = []
    ch_num = chapter_info.get("chapter", "?")
    ch_type = chapter_info.get("type", "normal")

    # 特殊类型：放宽检查
    if ch_type in ("afterword", "author_note"):
        summary = result.get("summary", "")
        if len(summary) < 20:  # 降低阈值
            errors.append(f"章节{ch_num}: 摘要过短({len(summary)}字)")
        # 不检查人物和张力
        return errors

    # 正文/番外：完整检查

    summary = result.get("summary", "")
    if len(summary) < 40:
        errors.append(f"章节{ch_num}: 摘要过短({len(summary)}字)")

    tension = result.get("tension_level")
    if tension is not None and not (1 <= tension <= 5):
        errors.append(f"章节{ch_num}: tension_level 不在 1-5 范围")

    if not result.get("characters_appear"):
        errors.append(f"章节{ch_num}: 未识别到出场人物")

    return errors


def _load_existing_chapters(novel_dir: Path) -> dict[int, dict]:
    """加载已分析的章节，用于断点续传。

    优先从 chapters/ 子目录读取（分析过程中的中间文件），
    如果不存在则读取 chapters.yaml（分析完成后的合并文件）。

    返回：
        dict：{章节号: 分析数据}
    """
    chapters_dir = novel_dir / "chapters"
    if chapters_dir.exists():
        result = {}
        for f in chapters_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "chapter" in data:
                result[data["chapter"]] = data
        if result:
            return result

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return {}
    with open(chapters_file, "r", encoding="utf-8") as f:
        existing = yaml.safe_load(f) or []
    return {ch["chapter"]: ch for ch in existing if isinstance(ch, dict) and "chapter" in ch}


def _append_chapter(novel_dir: Path, chapter_data: dict) -> None:
    """将单章分析结果写入独立文件。

    文件路径：chapters/{章节号}.yaml

    这样做的好处：
    - 每章分析完立即保存，中断也不会丢失
    - 不需要每次重写整个 chapters.yaml（性能更好）
    """
    chapters_dir = novel_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)
    ch_num = chapter_data["chapter"]
    chapter_file = chapters_dir / f"{ch_num:04d}.yaml"
    with open(chapter_file, "w", encoding="utf-8") as f:
        yaml.dump(chapter_data, f, allow_unicode=True, default_flow_style=False)


def _merge_chapters(novel_dir: Path, material_id: str = "") -> None:
    """合并所有独立章节文件为 chapters.yaml。

    在分析完成后调用，生成一个完整快照供其他脚本使用。
    """
    chapters_dir = novel_dir / "chapters"
    if not chapters_dir.exists():
        return
    all_chapters = []
    for f in sorted(chapters_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            all_chapters.append(data)
    all_chapters.sort(key=lambda x: x.get("chapter", 0))
    chapters_file = novel_dir / "chapters.yaml"
    with open(chapters_file, "w", encoding="utf-8") as f:
        yaml.dump(all_chapters, f, allow_unicode=True, default_flow_style=False)
    prefix = f"[{material_id}] " if material_id else ""
    logger.info(f"{prefix}已合并 {len(all_chapters)} 章 → chapters.yaml")


def _get_batch_size(config: dict) -> int:
    """读取批量大小配置，确保返回有效整数。"""
    raw = config["llm"].get("chapter_batch_size", 1)
    try:
        batch_size = int(raw)
    except (TypeError, ValueError):
        batch_size = 1
    return max(1, batch_size)


def _reanalyze_chapters(
    material_id: str,
    chapters: list[int],
    provider: str | None = None,
    use_window: bool = False,
    start_ch: int | None = None,
    end_ch: int | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> int:
    """重新分析指定章节（用于 summary 长度自动修复）。

    返回成功重新分析的章节数。
    """
    novel_dir = NOVELS_DIR / material_id
    config = load_config(provider)

    # 删除这些章节的分析文件（使用 04d 格式）
    for ch_num in chapters:
        ch_file = novel_dir / "chapters" / f"{ch_num:04d}.yaml"
        if ch_file.exists():
            ch_file.unlink()

    # 读取章节索引和原文
    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")

    # 构建待重新分析的章节列表
    batch_info = [
        ch for ch in chapter_index
        if ch["chapter"] in chapters
    ]

    if not batch_info:
        return 0

    # 滑动窗口模式：加载 evaluation.yaml 和已分析章节
    evaluation = None
    done: dict[int, dict] = {}
    if use_window:
        evaluation = load_evaluation(material_id)
        done = _load_existing_chapters(novel_dir)

    # 逐章重新分析
    success_count = 0
    total_to_reanalyze = len(batch_info)

    for ch_info in batch_info:
        ch_num = ch_info["chapter"]
        chapter_text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])

        try:
            # 构建滑动窗口上下文（如果启用）
            window_context = None
            if use_window:
                window_context = build_sliding_window_context(
                    ch_num, done, lines, chapter_index, evaluation
                )

            # 单章分析
            result = analyze_chapter(
                chapter_text,
                ch_info,
                config,
                progress_ratio=0.0,
                material_id=material_id,
                window_context=window_context,
            )

            result["chapter"] = ch_num
            result["title"] = ch_info["title"]
            result["type"] = ch_info.get("type", "normal")
            result["word_count"] = ch_info.get("word_count", 0)

            # 规范化 pacing
            if "pacing" in result:
                result["pacing"] = normalize_pacing(result["pacing"])

            # 写入章节文件（使用 _append_chapter 保持格式一致）
            _append_chapter(novel_dir, result)
            success_count += 1

            # 更新 done 字典（用于后续章节的窗口上下文）
            if use_window:
                done[ch_num] = result

        except Exception as e:
            logger.warning(f"[{material_id}] 重新分析第 {ch_num} 章失败: {e}")

        # 进度回调
        if progress_callback:
            progress_callback(
                success_count, total_to_reanalyze,
                f"重分析第 {ch_num} 章"
            )

    return success_count


def chapter_analyze(
    material_id: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
    start_ch: int | None = None,
    end_ch: int | None = None,
    provider: str | None = None,
    use_window: bool = False,
) -> bool:
    """对指定小说进行章节分析（支持断点续传和范围指定）。

    流程：
    1. 加载章节索引和原文
    2. 检查已分析的章节（断点续传）
    3. 过滤指定范围内的待处理章节
    4. 批量或逐章分析待处理章节
    5. 合并结果并执行质量检查

    参数：
        material_id：素材 ID（如 nm_novel_20240101_abc1）
        progress_callback：可选进度回调函数 (done: int, total: int, desc: str) -> None
        start_ch：起始章节号（可选，不指定则从第一章开始）
        end_ch：结束章节号（可选，不指定则到最后一章）
        provider：服务商名称（可选，不指定则使用默认配置）
        use_window：是否启用滑动窗口模式（可选，默认 False）
                   启用时会加载 evaluation.yaml 和前章摘要作为上下文

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
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "?")

    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    chapter_count = len(chapter_index)

    # 计算分析范围的起止章节号（用于进度比例计算）
    range_start = start_ch or 1
    range_end = end_ch or chapter_count

    # 输出小说基本信息和范围信息
    range_info = ""
    if start_ch is not None or end_ch is not None:
        range_info = f" | 分析范围: 第 {range_start}-{range_end} 章"
    window_info = " | 滑动窗口模式" if use_window else ""
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}{range_info}{window_info}")

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")

    # 滑动窗口模式：加载 evaluation.yaml
    evaluation = None
    if use_window:
        evaluation = load_evaluation(material_id)
        if evaluation:
            logger.info(f"[{material_id}] 已加载总体评估：{evaluation.get('novel_type', [])}")
        else:
            logger.warning(f"[{material_id}] 滑动窗口模式但未找到 evaluation.yaml，将无全局上下文")

    # 计算范围内的章节总数
    chapters_in_range = [
        ch for ch in chapter_index
        if (start_ch is None or ch["chapter"] >= start_ch)
        and (end_ch is None or ch["chapter"] <= end_ch)
    ]
    total = len(chapters_in_range)
    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    batch_size = _get_batch_size(config)

    # 滑动窗口模式：禁用批量处理（每章上下文不同）
    if use_window and batch_size > 1:
        logger.info(f"[{material_id}] 滑动窗口模式禁用批量处理，改为逐章分析")
        batch_size = 1

    # 标签校验去重：同一标签只警告一次（避免日志污染）
    warned_tags: set[str] = set()

    completed = 0
    skipped = 0
    total_downgrades = 0
    total_batch_errors = 0

    # 加载已分析的章节（断点续传）
    done = _load_existing_chapters(novel_dir)
    done_in_range = {
        ch_num: data for ch_num, data in done.items()
        if (start_ch is None or ch_num >= start_ch)
        and (end_ch is None or ch_num <= end_ch)
    }
    if done_in_range:
        if progress_callback:
            progress_callback(len(done_in_range), total, f"断点续传：已完成 {len(done_in_range)} 章")
        else:
            next_ch = max(done_in_range.keys()) + 1
            if start_ch and next_ch < start_ch:
                next_ch = start_ch
            logger.info(f"[{material_id}] 断点续传：已完成 {len(done_in_range)} 章，从第 {next_ch} 章继续")

    # 过滤出待处理章节（结合断点续传和范围指定）
    pending = [
        ch for ch in chapter_index
        if ch["chapter"] not in done
        and (start_ch is None or ch["chapter"] >= start_ch)
        and (end_ch is None or ch["chapter"] <= end_ch)
    ]
    skipped = total - len(pending)

    # ETA 估算：记录处理开始时间（跳过已完成章节后的真正起点）
    eta_start_time = time.monotonic() if pending else None

    if not pending:
        if progress_callback:
            progress_callback(total, total, "所有章节已完成")
        else:
            logger.info(f"[{material_id}] 所有 {total} 章已完成，跳过分析")
    else:
        n_batches = (len(pending) + batch_size - 1) // batch_size
        if progress_callback:
            progress_callback(skipped, total, f"待分析 {len(pending)} 章")
        else:
            logger.info(f"[{material_id}] 待分析: {len(pending)} 章，批量大小: {batch_size}，共 {n_batches} 批次")

    for batch_idx, batch_start in enumerate(range(0, len(pending), batch_size)):
        batch = pending[batch_start:batch_start + batch_size]
        first_ch = batch[0]["chapter"]
        last_ch = batch[-1]["chapter"]

        # 批次开始时的日志（非回调模式）
        if not progress_callback:
            progress_pct = (batch_idx * batch_size + skipped) / total * 100
            logger.info(
                f"[{material_id}] [批次 {batch_idx + 1}/{n_batches}] 第 {first_ch}-{last_ch} 章 "
                f"| 进度 {skipped + batch_idx * batch_size}/{total} ({progress_pct:.1f}%)"
            )

        batch_start_time = time.monotonic()
        batch_errors = 0
        batch_downgrades = 0
        batch_api_calls = 0

        # 批量分析
        batch_results: dict[int, dict] = {}
        use_batch_mode = batch_size > 1 and len(batch) > 1
        if use_batch_mode:
            try:
                batch_results = analyze_chapters_batch(
                    batch, lines, config, material_id,
                    batch_index=batch_idx,
                    total_batches=n_batches,
                    range_start_ch=range_start,
                    range_end_ch=range_end,
                )
                batch_api_calls += 1
                # 检查章节号是否匹配（不只是数量）
                expected_chapters = set(ch["chapter"] for ch in batch)
                returned_chapters = set(batch_results.keys())
                missing_in_batch = sorted(expected_chapters - returned_chapters)
                if missing_in_batch:
                    logger.warning(f"[{material_id}] 批量返回缺失 {len(missing_in_batch)} 章 {missing_in_batch}，降级为单章补齐")
            except Exception as e:
                logger.warning(f"[{material_id}] 批量分析失败: {e}，降级为逐章模式")
                batch_errors += 1
                batch_api_calls += 1

        # 处理每章结果
        for ch_info in batch:
            ch_num = ch_info["chapter"]
            result = batch_results.get(ch_num)
            window_context = None  # 显式初始化，避免作用域问题

            if result is None:
                # 批量失败或缺漏，改用单章分析
                batch_downgrades += 1
                if not progress_callback:
                    logger.info(f"[{material_id}] [降级单章] 第 {ch_num} 章: {ch_info['title']}（批量返回缺失）")
                chapter_text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])
                # 计算单章的进度比例
                ch_progress_ratio = (ch_num - range_start) / max(range_end - range_start + 1, 1)

                # 滑动窗口模式：构建窗口上下文
                if use_window:
                    window_context = build_sliding_window_context(
                        ch_num, done, lines, chapter_index, evaluation
                    )

                try:
                    result = analyze_chapter(
                        chapter_text, ch_info, config,
                        progress_ratio=ch_progress_ratio,
                        material_id=material_id,
                        window_context=window_context,
                    )
                    batch_api_calls += 1
                except Exception as e:
                    logger.error(f"[{material_id}] 第 {ch_num} 章分析失败（已重试耗尽）: {e}")
                    batch_errors += 1
                    continue

            # 检查结果质量
            errors = validate_chapter_analysis(result, ch_info)
            for err in errors:
                logger.warning(f"[{material_id}] [质量] {err}")
                batch_errors += 1

            # 滑动窗口模式：校验窗口字段
            if use_window and window_context:
                window_errors = validate_window_fields(result, window_context.get("prev_tension_level"))
                for err in window_errors:
                    logger.warning(f"[{material_id}] [窗口] {err}")
                    batch_errors += 1

            # 章节级标签校验（阶段四新增）
            tags_errors = validate_chapter_tags_fields(result)
            for err in tags_errors:
                # 去重：同一标签只警告一次
                if err not in warned_tags:
                    warned_tags.add(err)
                    logger.warning(f"[{material_id}] [标签] {err}")
                batch_errors += 1

            result["chapter"] = ch_num
            result["title"] = ch_info["title"]
            result["type"] = ch_info.get("type", "normal")  # 从索引中获取章节类型
            result["word_count"] = ch_info.get("word_count", 0)  # 从索引中获取正确字数，防御性取值

            # 规范化 pacing（LLM 输出变体 → 标准值）
            if "pacing" in result:
                original = result["pacing"]
                normalized = normalize_pacing(original)
                if normalized != original:
                    logger.info(f"[{material_id}] pacing 规范化: '{original}' → '{normalized}'")
                result["pacing"] = normalized

            # 立即保存（断点续传关键）
            _append_chapter(novel_dir, result)
            completed += 1

            # 更新 done 字典（用于滑动窗口的下一章上下文）
            done[ch_num] = result

            # 进度更新：在每章完成后更新（含 ETA 估算）
            if progress_callback:
                total_done = skipped + completed
                remaining = total - total_done
                desc = f"第 {first_ch}-{last_ch} 章 ({batch_idx + 1}/{n_batches})"

                # ETA 估算：已耗时 × 剩余比例（至少完成 1 后才显示）
                if eta_start_time and total_done > skipped and remaining > 0:
                    elapsed = time.monotonic() - eta_start_time
                    new_done = total_done - skipped  # 本次运行实际完成的章数
                    eta_sec = elapsed * remaining / new_done
                    desc += f" | ETA ~{_fmt_duration(eta_sec)}"

                progress_callback(total_done, total, desc)

        # 批次耗时汇总
        batch_elapsed = time.monotonic() - batch_start_time
        total_downgrades += batch_downgrades
        total_batch_errors += batch_errors
        if not progress_callback:
            finish_reason = get_last_call_finish_reason()
            logger.info(
                f"[{material_id}] 批次#{batch_idx + 1} 完成: {batch_elapsed:.1f}s | "
                f"返回 {len(batch_results)}/{len(batch)} 章 | "
                f"降级 {batch_downgrades} 次 | 错误 {batch_errors} 次 | "
                f"finish={finish_reason}"
            )

        # 批次间等待（避免触发速率限制）
        if batch_start + batch_size < len(pending):
            time.sleep(rate_limit)

    if progress_callback:
        progress_callback(total, total, f"完成: {completed} 章")
    else:
        logger.info(f"[{material_id}] 章级分析完成: 新分析 {completed} 章，跳过已完成 {skipped} 章，共 {total} 章")
        if total_downgrades > 0:
            total_chapters_attempted = n_batches * batch_size if pending else 1
            downgrade_rate = total_downgrades / total_chapters_attempted * 100
            logger.info(
                f"[{material_id}] 降级统计: {total_downgrades} 次降级（占 {downgrade_rate:.1f}%），"
                f"批次错误 {total_batch_errors} 次"
            )

    # 合并所有章节文件
    _merge_chapters(novel_dir, material_id=material_id)

    # 质量检查（带 summary 长度自动修复）
    max_summary_retries = 3
    final_passed = False

    for retry_idx in range(max_summary_retries):
        logger.info(f"[{material_id}] 执行章级分析质量校验...")
        if run_quality_check(material_id, start_ch=start_ch, end_ch=end_ch):
            final_passed = True
            break

        # 检查是否有 summary 长度不够的章节（应用范围过滤）
        short_chapters = get_short_summary_chapters(material_id, start_ch=start_ch, end_ch=end_ch)
        if not short_chapters:
            # 不是 summary 问题，无法自动修复
            update_meta_status(material_id, "failed")
            raise ValueError(f"章级分析质量校验未通过：{material_id}")

        # 自动重新分析这些章节
        logger.info(
            f"[{material_id}] 发现 {len(short_chapters)} 章 summary 长度不足，"
            f"自动重新分析（第 {retry_idx + 1}/{max_summary_retries} 次）"
        )
        success = _reanalyze_chapters(
            material_id, short_chapters,
            provider=provider,
            use_window=use_window,
            start_ch=start_ch,
            end_ch=end_ch,
            progress_callback=progress_callback
        )
        if success < len(short_chapters):
            logger.warning(f"[{material_id}] 重分析部分失败：成功 {success}/{len(short_chapters)} 章")
        _merge_chapters(novel_dir, material_id=material_id)

    # 循环未通过时的最终校验
    if not final_passed:
        if not run_quality_check(material_id, start_ch=start_ch, end_ch=end_ch):
            update_meta_status(material_id, "failed")
            raise ValueError(f"章级分析质量校验未通过（已重试 {max_summary_retries} 次）：{material_id}")

    update_meta_status(material_id, "analyzed")

    return True


def repair_short_summaries(
    material_id: str,
    short_chapters: list[int] | None = None,
    provider: str | None = None,
    use_window: bool = False,
    min_success_rate: float = 0.8,
) -> tuple[bool, int, int]:
    """修复 summary 长度不足的章节（公开接口）。

    参数：
        material_id: 素材 ID
        short_chapters: 需要修复的章节列表（None 则自动检测）
        provider: LLM 服务商（应与原始分析一致）
        use_window: 是否使用滑动窗口（应与原始分析一致）
        min_success_rate: 最低成功率阈值（低于此值视为失败）

    返回：
        tuple: (是否成功修复, 成功章数, 总需修复章数)
    """
    if short_chapters is None:
        short_chapters = get_short_summary_chapters(material_id)

    if not short_chapters:
        return True, 0, 0

    novel_dir = NOVELS_DIR / material_id
    success_count = _reanalyze_chapters(
        material_id,
        short_chapters,
        provider=provider,
        use_window=use_window,
    )
    total = len(short_chapters)

    # 合并章节文件
    _merge_chapters(novel_dir, material_id=material_id)

    # 判断是否成功（成功率 >= min_success_rate）
    success_rate = success_count / total if total > 0 else 1.0
    success = success_rate >= min_success_rate

    if not success:
        logger.warning(
            f"[{material_id}] 修复成功率 {success_rate:.1%} 低于阈值 {min_success_rate:.1%}"
        )

    return success, success_count, total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze.py <material_id>")
        sys.exit(1)

    chapter_analyze(sys.argv[1])