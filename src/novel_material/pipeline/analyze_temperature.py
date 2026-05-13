"""章节分析动态温度控制：独立算法，无 IO 操作。

此模块包含 analyze 流水线所需的动态温度和提示词策略，
用于根据分析进度调整 LLM 参数以提升输出多样性。
"""
from novel_material.pipeline.analyze_utils import _SYSTEM_PROMPT


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


__all__ = [
    "_build_dynamic_system_prompt",
    "_should_use_thinking_mode",
    "_calculate_dynamic_temperature",
]