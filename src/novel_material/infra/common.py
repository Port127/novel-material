"""公共函数与常量模块。

位置说明：
- infra 是基础设施层，不依赖其他业务模块
- validation、pipeline、tags、storage、material 等都可以安全导入 infra/common

提供的公共工具：
1. 常量：章节结构标记、小说类型、张力变化、钩子类型等合法值集合
2. 函数：章节类型判断、素材 ID 生成、章节过滤等
"""
import random
import string
from datetime import datetime
from pathlib import Path


# ============================================================
# 常量定义（从 constants.py 合入）
# ============================================================

# 章节结构角色标记的合法值（由代码推断）
KEY_PLOT_POINT_VALUES = [
    "inciting_incident",
    "first_turning_point",
    "midpoint",
    "second_turning_point",
    "climax",
    "resolution",
]

# 小说类型的合法值（用于总体评估）
NOVEL_TYPE_VALUES = [
    "玄幻",
    "奇幻",
    "武侠",
    "仙侠",
    "都市",
    "现实",
    "军事",
    "历史",
    "游戏",
    "科幻",
    "灵异",
    "悬疑",
    "其他",
]

# 张力变化方向的合法值（滑动窗口分析）
TENSION_CHANGE_VALUES = [
    "上升",
    "持平",
    "下降",
]

# 章末钩子类型的合法值
HOOK_TYPE_VALUES = [
    "悬念钩子",
    "反转钩子",
    "情感钩子",
    "信息钩子",
    "危机钩子",
    "无钩子",
]

# 特殊章节类型（不参与正文分析、统计、同步）
SPECIAL_CHAPTER_TYPES = ("afterword", "author_note")

# 有效章节类型（参与正文分析）
VALID_CHAPTER_TYPES = ("normal", "extra")


# ============================================================
# 公共函数
# ============================================================

def is_special_chapter_type(ch_type: str) -> bool:
    """判断章节是否为特殊类型（不参与正文分析）。

    特殊类型包括：
    - afterword：后记/完本感言
    - author_note：作者说/作者的话

    Args:
        ch_type: 章节类型字符串

    Returns:
        True 表示特殊类型，应跳过；False 表示正文类型
    """
    return ch_type in SPECIAL_CHAPTER_TYPES


def is_valid_chapter_type(ch_type: str) -> bool:
    """判断章节是否为有效正文类型。

    有效类型包括：
    - normal：正文章节
    - extra：番外/外传

    Args:
        ch_type: 章节类型字符串

    Returns:
        True 表示正文类型；False 表示特殊类型
    """
    return ch_type in VALID_CHAPTER_TYPES


def filter_normal_chapters(chapters_data: list) -> list:
    """过滤出正文章节，排除特殊类型。

    Args:
        chapters_data: 章节数据列表，每项需包含 type 字段

    Returns:
        过滤后的章节数据列表，仅包含 normal 和 extra 类型
    """
    return [
        ch for ch in chapters_data
        if is_valid_chapter_type(ch.get("type", "normal"))
    ]


def generate_material_id(novels_dir: Path | None = None) -> str:
    """生成唯一的素材 ID，确保不与已有 ID 冲突。

    格式：nm_novel_YYYYMMDD_xxxx（xxxx 为随机字母数字）

    Args:
        novels_dir: 小说目录路径（用于冲突检测），可选

    Returns:
        唯一的素材 ID 字符串
    """
    date_str = datetime.now().strftime("%Y%m%d")
    max_attempts = 10

    for _ in range(max_attempts):
        random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        material_id = f"nm_novel_{date_str}_{random_str}"

        # 如果提供了目录，检查是否已存在
        if novels_dir is not None:
            if not (novels_dir / material_id).exists():
                return material_id
        else:
            # 无目录时直接返回（调用方自行确保唯一性）
            return material_id

    # 极端情况：多次冲突，增加随机字符串长度
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"nm_novel_{date_str}_{random_str}"