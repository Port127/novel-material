"""章节分析辅助函数：提示词模板、配置读取、滑动窗口上下文构建。

此模块包含 analyze 流水线所需的核心常量和辅助函数，
供 analyze_single.py、analyze_batch.py 和 analyze.py 使用。

拆分后的子模块：
- analyze_validators.py：校验函数（纯逻辑，无 IO）
- analyze_files.py：文件操作（只做 IO）
- analyze_temperature.py：动态温度控制（独立算法）
"""
import time
from pathlib import Path

from novel_material.infra.config import get_settings
from novel_material.infra.llm import truncate_to_tokens
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()


# ============================================================
# 常量：LLM 提示词模板
# ============================================================

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
- tension_change：张力变化方向，必须根据前章张力值计算（重要）：
  - 前章张力 > 当前张力 → "下降"
  - 前章张力 < 当前张力 → "上升"
  - 前章张力 = 当前张力 → "持平"
  注意：tension_level 与 tension_change 必须一致
- emotion_transition：情感过渡描述（10-50字）
- plot_progress：情节进度描述（20-100字）"""

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


# ============================================================
# 辅助函数：配置读取
# ============================================================

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


def _get_batch_size(config: dict) -> int:
    """读取批量大小配置，确保返回有效整数。"""
    raw = config["llm"].get("chapter_batch_size", 1)
    try:
        batch_size = int(raw)
    except (TypeError, ValueError):
        batch_size = 1
    return max(1, batch_size)


# ============================================================
# 辅助函数：滑动窗口上下文
# ============================================================

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


# ============================================================
# 导出列表
# ============================================================

__all__ = [
    # 常量
    "_SYSTEM_PROMPT",
    "_CHAPTER_JSON_SCHEMA",
    "_CHAPTER_JSON_SCHEMA_WITH_WINDOW",
    "_BATCH_JSON_SCHEMA",
    # 辅助函数
    "_fmt_duration",
    "_get_max_chapter_tokens",
    "_get_batch_size",
    "build_sliding_window_context",
]