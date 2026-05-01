#!/usr/bin/env python
"""流水线调度：串联入库、分析、同步数据库全流程。"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.core.ingest import ingest_file
from scripts.core.chapter_analyze import chapter_analyze
from scripts.core.sync_db import sync_novel
from scripts.analyze.generate_outline import generate_outline
from scripts.analyze.generate_worldbuilding import generate_worldbuilding
from scripts.analyze.generate_characters import generate_characters
from scripts.analyze.generate_tags import generate_tags
from scripts.utils.refine import refine

def pipeline_full(file_path):
    """完整流水线：入库 → 分析 → 同步数据库。"""
    print("=" * 60)
    print("开始完整流水线")
    print("=" * 60)

    # 1. 入库
    print("\n[1/4] 入库阶段")
    material_id = ingest_file(file_path)
    if not material_id:
        print("入库失败，终止流水线")
        return

    time.sleep(1)

    # 2. 骨架分析
    print("\n[2/4] 骨架分析阶段（大纲/世界观/人物/标签）")
    generate_outline(material_id)
    time.sleep(1)
    generate_worldbuilding(material_id)
    time.sleep(1)
    generate_characters(material_id)
    time.sleep(1)
    generate_tags(material_id)

    time.sleep(1)

    # 3. 章级分析
    print("\n[3/4] 章级分析阶段")
    chapter_analyze(material_id)

    time.sleep(1)

    # 4. 同步数据库
    print("\n[4/4] 同步数据库阶段")
    sync_novel(material_id)

    print("\n" + "=" * 60)
    print(f"完整流水线完成! material_id: {material_id}")
    print("=" * 60)

def pipeline_analyze(material_id):
    """分析流水线：大纲/世界观/人物/标签/章级。"""
    print("=" * 60)
    print("开始分析流水线")
    print("=" * 60)

    print("\n[1/5] 大纲生成")
    generate_outline(material_id)
    time.sleep(1)

    print("\n[2/5] 世界观提取")
    generate_worldbuilding(material_id)
    time.sleep(1)

    print("\n[3/5] 人物提取")
    generate_characters(material_id)
    time.sleep(1)

    print("\n[4/5] 标签生成")
    generate_tags(material_id)
    time.sleep(1)

    print("\n[5/5] 章级分析")
    chapter_analyze(material_id)

    time.sleep(1)

    # 同步数据库
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
        print("  python pipeline.py full <文件路径>       # 完整流水线")
        print("  python pipeline.py analyze <material_id> # 分析流水线")
        print("  python pipeline.py finalize <material_id> # 收尾流水线")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "full":
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
        print("可用模式: full, analyze, finalize")
        sys.exit(1)
