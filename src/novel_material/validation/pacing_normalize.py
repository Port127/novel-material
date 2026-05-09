"""Pacing 规范化：将 LLM 输出的变体映射到标准值。

目的：
- LLM 输出的 pacing 值常有同义词/变体（如 "中等"、"轻快"）
- 自动映射到标准集合，保持数据一致性
- 新变体只需添加映射表，无需改校验逻辑
"""

# 核心标准集合（用于统计和校验）
PACING_CORE = {
    "快", "慢", "喘息", "加速", "中", "平稳",
    # 扩展中间值
    "极快", "平缓", "中慢", "缓", "适中", "中快",
    # 转换型
    "慢转快", "快转缓",
}

# 变体 → 标准值映射表（可持续累积）
PACING_NORMALIZE_MAP = {
    # 中间态同义词
    "中等": "中",
    "轻快": "中快",
    "明快": "中快",
    "舒缓": "缓",
    "缓慢": "慢",
    "轻松": "缓",
    "紧张": "中快",  # 情绪紧张但节奏未必极快
    # 转换型变体
    "极快转缓": "快转缓",
    "极快转中": "快转缓",
    "由缓转紧": "慢转快",
    "张弛有度": "慢转快",  # 节奏动态变化
}


def normalize_pacing(value: str | None) -> str | None:
    """规范化 pacing 值到标准集合。

    参数：
        value: LLM 输出的原始 pacing 值

    返回：
        规范化后的标准值，若已是标准值则不变，若无法映射则返回原值（兼容性优先）
    """
    if value is None:
        return None

    # 已是标准值，无需转换
    if value in PACING_CORE:
        return value

    # 映射表中有定义
    if value in PACING_NORMALIZE_MAP:
        return PACING_NORMALIZE_MAP[value]

    # 未知变体：返回原值（让 schema 校验捕获，人工补充映射表）
    return value