"""大纲生成：LLM 基于章级摘要池生成故事大纲结构（幕/序列/节拍/钩子网络）。

注意：此脚本必须在 analyze 完成后运行，需要 chapters.yaml 作为全局视角输入。

规模适配：
- 摘要池采用分层均匀采样（> 200 章时），确保全书首尾及中间均有代表
- beats 生成拆分为 per-sequence 循环：每个序列独立调用 LLM，避免一次性输出 1000+ 条被截断

统计驱动：
- 张力分布：识别高潮章节，指导序列划分
- 悬念分布：识别钩子节点，指导节奏控制

模块拆分：
- outline_temp.py：临时文件管理（断点续传）
- outline_stats.py：大纲统计函数
- outline_acts.py：幕序列生成
- outline_beats.py：节拍生成
- outline_core.py：入口函数
- outline.py：统一入口
"""
import sys

# 从子模块导入所有函数，向后兼容
from novel_material.pipeline.outline_core import generate_outline
from novel_material.pipeline.outline_acts import generate_simple_acts


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python outline.py <material_id>")
        sys.exit(1)

    generate_outline(sys.argv[1])