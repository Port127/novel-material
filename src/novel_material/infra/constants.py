"""公共常量定义：各模块共享的枚举值、合法值集合。

位置说明：
- infra 是基础设施层，不依赖其他业务模块
- validation、pipeline、tags 等都可以安全导入 infra/constants
"""

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
# 来源：tags.yaml 的 genre_primary
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

# 章末钩子类型的合法值（阶段四新增）
HOOK_TYPE_VALUES = [
    "悬念钩子",
    "反转钩子",
    "情感钩子",
    "信息钩子",
    "危机钩子",
    "无钩子",
]
