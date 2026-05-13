"""单章分析：调用 LLM 分析单个章节内容。

此模块包含 analyze_chapter 函数，供 analyze.py 入口调用。
依赖 analyze_utils.py 中的辅助函数和常量。
"""
from novel_material.infra.llm import truncate_to_tokens
from novel_material.pipeline.analyze_utils import (
    _SYSTEM_PROMPT,
    _CHAPTER_JSON_SCHEMA,
    _CHAPTER_JSON_SCHEMA_WITH_WINDOW,
    _get_max_chapter_tokens,
)
from novel_material.pipeline.analyze_temperature import (
    _build_dynamic_system_prompt,
    _should_use_thinking_mode,
    _calculate_dynamic_temperature,
)


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
    from novel_material.infra.llm import call_llm

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