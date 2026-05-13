"""大纲生成入口：结构 + 序列 + 节拍 + 钩子网络。

此模块包含 generate_outline 主函数，
调用 outline_logic.py 和 outline_io.py 完成大纲生成任务。

两阶段策略：
1. 全局一次：基于分层摘要池生成前提/主题/基调 + 幕/序列划分
2. per-sequence 循环：为每个序列独立生成 beats，上下文聚焦，输出量可控
"""
import sys
from collections.abc import Callable

from novel_material.pipeline.outline_logic import init_outline_context, run_outline_pipeline


def generate_outline(
    material_id: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
    provider: str | None = None,
) -> bool:
    """生成大纲：结构 + 序列 + 节拍 + 钩子网络（入口函数）。

    参数：
        material_id: 素材 ID
        progress_callback: 可选进度回调函数 (done: int, total: int, desc: str) -> None
        provider: 服务商名称（可选，不指定则使用默认配置）

    返回：
        True 表示成功，False 表示失败
    """
    ctx = init_outline_context(material_id, provider)
    if ctx is None:
        return False
    return run_outline_pipeline(ctx, progress_callback, material_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python outline_core.py <material_id>")
        sys.exit(1)
    generate_outline(sys.argv[1])