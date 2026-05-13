"""章节分析辅助函数：提示词构建、温度控制、滑动窗口、文件操作等。

此模块包含 analyze 流水线所需的所有辅助函数和常量，
供 analyze_single.py、analyze_batch.py 和 analyze.py 使用。
"""
import yaml
import time
from pathlib import Path

from novel_material.infra.config import get_settings
from novel_material.infra.llm import truncate_to_tokens
from novel_material.infra.progress import get_pipeline_logger
from novel_material.infra.common import TENSION_CHANGE_VALUES

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
# 辅助函数：动态提示词与温度控制
# ============================================================

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


# ============================================================
# 辅助函数：结果校验
# ============================================================

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


# ============================================================
# 辅助函数：文件操作（断点续传）
# ============================================================

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


# ============================================================
# 导出常量供子模块使用
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
    "_build_dynamic_system_prompt",
    "_should_use_thinking_mode",
    "_calculate_dynamic_temperature",
    "build_sliding_window_context",
    "validate_window_fields",
    "validate_chapter_analysis",
    "_load_existing_chapters",
    "_append_chapter",
    "_merge_chapters",
]