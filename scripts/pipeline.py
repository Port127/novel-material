#!/usr/bin/env python
"""流水线调度：串联入库、分析、同步数据库全流程。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.core.ingest import ingest_file
from scripts.core.chapter_analyze import chapter_analyze
from scripts.core.embed_chapters import embed_chapters
from scripts.core.sync_db import sync_novel
from scripts.analyze.generate_outline import generate_outline
from scripts.analyze.generate_worldbuilding import generate_worldbuilding
from scripts.analyze.generate_characters import generate_characters
from scripts.analyze.generate_tags import generate_tags
from scripts.utils.refine import refine

def pipeline_ingest(file_path):
    """入库流水线：预处理 + 章节切分，生成 source.txt / chapter_index.yaml / meta.yaml。"""
    print("=" * 60)
    print("开始入库流水线")
    print("=" * 60)

    material_id = ingest_file(file_path)
    if not material_id:
        print("入库失败")
        return None

    print("\n" + "=" * 60)
    print(f"入库完成! material_id: {material_id}")
    print("=" * 60)
    return material_id


def pipeline_full(file_path):
    """完整流水线：入库 → 章级分析 → 骨架分析 → 同步数据库。

    执行顺序（已修正 A1）：
      ingest → chapter_analyze → outline/worldbuilding/characters/tags → sync
    章级分析前置，确保大纲/世界观/人物/标签使用全书摘要池而非原文片段。
    """
    print("=" * 60)
    print("开始完整流水线")
    print("=" * 60)

    # 1. 入库
    print("\n[1/5] 入库阶段")
    material_id = ingest_file(file_path)
    if not material_id:
        print("入库失败，终止流水线")
        return

    time.sleep(1)

    # 2. 章级分析（前置，为后续骨架分析提供全书摘要池）
    print("\n[2/6] 章级分析阶段（为骨架分析提供全书视角）")
    chapter_analyze(material_id)

    time.sleep(1)

    # 3. 章节向量化
    print("\n[3/6] 向量化阶段")
    embed_chapters(material_id)

    time.sleep(1)

    # 4. 骨架分析（基于章级摘要池）
    print("\n[4/6] 骨架分析阶段（大纲/世界观/人物/标签）")
    generate_outline(material_id)
    time.sleep(1)
    generate_worldbuilding(material_id)
    time.sleep(1)
    generate_characters(material_id)
    time.sleep(1)
    generate_tags(material_id)

    time.sleep(1)

    # 5. 精调
    print("\n[5/6] 精调阶段")
    refine(material_id)

    time.sleep(1)

    # 6. 同步数据库
    print("\n[6/6] 同步数据库阶段")
    sync_novel(material_id)

    print("\n" + "=" * 60)
    print(f"完整流水线完成! material_id: {material_id}")
    print("=" * 60)


def pipeline_analyze(material_id):
    """分析流水线：章级分析 → 大纲/世界观/人物/标签。

    执行顺序（已修正 A1）：chapter_analyze 前置。
    """
    print("=" * 60)
    print("开始分析流水线")
    print("=" * 60)

    print("\n[1/5] 章级分析（全书视角基础）")
    chapter_analyze(material_id)
    time.sleep(1)

    print("\n[2/5] 大纲生成")
    generate_outline(material_id)
    time.sleep(1)

    print("\n[3/5] 世界观提取")
    generate_worldbuilding(material_id)
    time.sleep(1)

    print("\n[4/5] 人物提取")
    generate_characters(material_id)
    time.sleep(1)

    print("\n[5/5] 标签生成")
    generate_tags(material_id)
    time.sleep(1)

    print("\n同步数据库...")
    sync_novel(material_id)

    print("\n" + "=" * 60)
    print("分析流水线完成!")
    print("=" * 60)

def pipeline_finalize(material_id):
    """收尾流水线：精调 + 同步数据库。"""
    print("=" * 60)
    print("开始收尾流水线")
    print("=" * 60)

    print("\n[1/2] 精调")
    refine(material_id)
    time.sleep(1)

    print("\n[2/2] 同步数据库")
    sync_novel(material_id)

    print("\n" + "=" * 60)
    print("收尾流水线完成!")
    print("=" * 60)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python pipeline.py ingest  <文件路径>       # 入库（预处理+章节切分）")
        print("  python pipeline.py full    <文件路径>       # 完整流水线")
        print("  python pipeline.py analyze <material_id>   # 分析流水线")
        print("  python pipeline.py finalize <material_id>  # 收尾流水线")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "ingest":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py ingest <文件路径>")
            sys.exit(1)
        pipeline_ingest(sys.argv[2])
    elif mode == "full":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py full <文件路径>")
            sys.exit(1)
        pipeline_full(sys.argv[2])
    elif mode == "analyze":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py analyze <material_id>")
            sys.exit(1)
        pipeline_analyze(sys.argv[2])
    elif mode == "finalize":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py finalize <material_id>")
            sys.exit(1)
        pipeline_finalize(sys.argv[2])
    else:
        print(f"未知模式: {mode}")
        print("可用模式: ingest, full, analyze, finalize")
        sys.exit(1)
