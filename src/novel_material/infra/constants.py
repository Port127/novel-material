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