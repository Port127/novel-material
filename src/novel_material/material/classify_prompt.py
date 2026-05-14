"""分类提示词模板。

分类是前置环节，使用动态 genre 映射（从数据库加载）。
"""


def build_classify_prompt(genre_list: list[str]) -> str:
    """动态构建分类提示词，genre_list 来自系统标签体系。

    Args:
        genre_list: 一级题材列表（从数据库加载）

    Returns:
        str: 系统提示词
    """
    # 取前 20 个一级题材（避免 prompt 过长）
    genre_text = "\n".join(f"- {g}" for g in genre_list[:20])

    SYSTEM_PROMPT = f"""你是小说类型分类专家。根据小说样本内容，分析题材、元素、风格、质量。

输出格式（JSON）：
{{"genre_primary": "一级题材", "genre_secondary": "二级题材（可选）", "genre_description": "一句话描述小说类型特点", "elements": ["核心元素1", "核心元素2"], "elements_description": "元素特点描述", "style": {{\"narrative\": \"叙事风格\", \"tone\": \"情感基调\", \"pace\": \"节奏类型\"}}, "quality": {{\"writing\": 4, \"plot\": 4, \"character\": 4}}, "confidence": 0.8}}

一级题材取值范围：
{genre_text}

选择规则：
1. 必须选择一个一级题材
2. 二级题材可选，但需与一级题材匹配
3. elements 取 2-5 个核心元素（如：重生、系统、逆袭、穿越、修炼）
4. style 各字段：narrative（快节奏/慢热/日常），tone（热血/冷峻/温馨），pace（紧凑/舒缓）
5. quality 各字段评分 1-5，综合反映文笔、剧情、人物塑造
6. confidence 表示分类置信度（0.0-1.0）"""

    return SYSTEM_PROMPT


USER_PROMPT_TEMPLATE = """小说标题：{title}
作者：{author}

采样章节内容（开头 + 中间 + 后期）：
{content}

请根据以上样本内容分析并输出分类结果。
注意：样本可能包含开头设定、中间发展和后期转折，综合判断题材、元素和风格。"""


__all__ = [
    "build_classify_prompt",
    "USER_PROMPT_TEMPLATE",
]