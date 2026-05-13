"""存储层修复模块：章节重分析委托接口。

此模块作为 storage 层的修复入口，通过调用 pipeline.analyze 的公开接口执行修复，
避免 storage 层直接依赖 pipeline 层的具体实现细节。

职责：
- 提供 storage 层的修复入口函数
- 委托实际修复逻辑给 pipeline.analyze
- 处理修复结果的日志记录
"""
from novel_material.infra.progress import get_pipeline_logger
from novel_material.pipeline.analyze import reanalyze_chapters

logger = get_pipeline_logger()


def repair_chapters(
    material_id: str,
    chapters: list[int] | None = None,
    provider: str | None = None,
    use_window: bool = False,
    min_success_rate: float = 0.8,
) -> tuple[bool, int, int]:
    """修复指定章节（storage 层入口）。

    委托实际修复逻辑给 pipeline.analyze.reanalyze_chapters。

    参数：
        material_id: 素材 ID
        chapters: 需要重分析的章节列表（None 则自动检测问题章节）
        provider: LLM 服务商（应与原始分析一致）
        use_window: 是否使用滑动窗口（应与原始分析一致）
        min_success_rate: 最低成功率阈值（低于此值视为失败）

    返回：
        tuple: (是否成功, 成功章数, 总需重分析章数)
    """
    success, repaired, total = reanalyze_chapters(
        material_id,
        chapters=chapters,
        provider=provider,
        use_window=use_window,
        min_success_rate=min_success_rate,
    )

    if success:
        logger.info(f"[{material_id}] 修复完成: {repaired}/{total} 章")
    else:
        logger.warning(f"[{material_id}] 修复失败: {repaired}/{total} 章 (成功率 < {min_success_rate:.0%})")

    return success, repaired, total


# 向后兼容别名
def repair_short_summaries(
    material_id: str,
    short_chapters: list[int] | None = None,
    provider: str | None = None,
    use_window: bool = False,
    min_success_rate: float = 0.8,
) -> tuple[bool, int, int]:
    """修复 summary 长度不足的章节（向后兼容接口）。

    已更名为 repair_chapters，请使用新函数名。
    """
    return repair_chapters(
        material_id,
        chapters=short_chapters,
        provider=provider,
        use_window=use_window,
        min_success_rate=min_success_rate,
    )