#!/usr/bin/env python
"""质量校验脚本：检查章级分析结果的完整性。"""
import os
import sys
import yaml
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

def validate_chapters(material_id):
    """校验章级分析结果。"""
    novel_dir = Path("data/novels") / material_id
    chapters_file = novel_dir / "chapters.yaml"

    if not chapters_file.exists():
        print(f"错误: chapters.yaml 不存在: {chapters_file}")
        return False

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        print(f"警告: {material_id} 没有章节分析数据")
        return False

    errors = []
    warnings = []

    for ch in chapters:
        ch_num = ch.get("chapter", "?")
        title = ch.get("title", "?")

        # 摘要长度
        summary = ch.get("summary", "")
        if len(summary) < 20:
            errors.append(f"  第{ch_num}章: 摘要过短 ({len(summary)}字)")
        elif len(summary) > 200:
            warnings.append(f"  第{ch_num}章: 摘要过长 ({len(summary)}字)")

        # 张力等级
        tension = ch.get("tension_level")
        if tension is None:
            errors.append(f"  第{ch_num}章: 缺失 tension_level")
        elif not (1 <= tension <= 5):
            errors.append(f"  第{ch_num}章: tension_level={tension} 不在 1-5 范围")

        # 出场人物
        chars = ch.get("characters_appear", [])
        if not chars:
            errors.append(f"  第{ch_num}章: 未识别到出场人物")

        # 章节功能
        funcs = ch.get("chapter_function", ch.get("chapter_functions", []))
        if not funcs:
            warnings.append(f"  第{ch_num}章: 未标注章节功能")

    if errors:
        print(f"\n发现 {len(errors)} 个错误:")
        for e in errors:
            print(e)

    if warnings:
        print(f"\n发现 {len(warnings)} 个警告:")
        for w in warnings:
            print(w)

    if not errors:
        print(f"校验通过: {material_id} ({len(chapters)}章)")
        return True
    else:
        print(f"校验失败: {len(errors)} 个错误需要修复")
        return False

def load_tags_dict():
    """加载标签字典。"""
    tags_file = Path("data/tags.yaml")
    if tags_file.exists():
        with open(tags_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def validate_tags(material_id):
    """校验标签是否都在字典范围内。"""
    tags_dict = load_tags_dict()
    if not tags_dict:
        print("警告: 标签字典不存在，跳过标签校验")
        return True

    novel_dir = Path("data/novels") / material_id
    chapters_file = novel_dir / "chapters.yaml"

    if not chapters_file.exists():
        return False

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    invalid_tags = []
    for ch in chapters:
        funcs = ch.get("chapter_function", ch.get("chapter_functions", []))
        for func in funcs:
            # 检查是否在 chapter_function 标签维度中
            valid_funcs = tags_dict.get("chapter_function", [])
            if isinstance(valid_funcs, list) and func not in valid_funcs:
                invalid_tags.append(f"  第{ch.get('chapter', '?')}章: '{func}' 不在字典中")

    if invalid_tags:
        print(f"\n发现 {len(invalid_tags)} 个非法标签:")
        for t in invalid_tags:
            print(t)
        return False
    else:
        print("标签校验通过")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python quality_check.py <material_id>")
        sys.exit(1)

    material_id = sys.argv[1]
    validate_chapters(material_id)
    validate_tags(material_id)
