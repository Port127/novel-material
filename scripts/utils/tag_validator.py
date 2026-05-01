#!/usr/bin/env python
"""标签合法性校验工具：检查事件/章节标签是否在字典范围内。"""
import sys
import yaml
from pathlib import Path
from scripts.core.paths import NOVELS_DIR, TAGS_FILE

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

VALID_DIMENSIONS = [
    "channel",      # L0 频道
    "genre",        # L1-L2 题材
    "element",      # L3 元素
    "character",    # 角色
    "style",        # 风格
    "structure",    # 结构
    "setting",      # 世界观
    "chapter_function"  # 章节功能
]

def load_tags_dict():
    """加载标签字典。"""
    tags_file = TAGS_FILE
    if not tags_file.exists():
        print("错误: 标签字典不存在")
        return None

    with open(tags_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def check_dimension(dimension):
    """检查某个维度的标签使用情况。"""
    tags_dict = load_tags_dict()
    if not tags_dict:
        return

    valid_set = set()
    dim_data = tags_dict.get(dimension, {})
    if isinstance(dim_data, list):
        valid_set = set(dim_data)
    elif isinstance(dim_data, dict):
        # 递归收集所有值
        def collect_values(d):
            vals = set()
            for k, v in d.items():
                vals.add(k)
                if isinstance(v, list):
                    vals.update(v)
                elif isinstance(v, dict):
                    vals.update(collect_values(v))
            return vals
        valid_set = collect_values(dim_data)

    # 扫描所有章节文件，收集使用的标签
    used_tags = set()
    novels_dir = NOVELS_DIR
    for novel_dir in novels_dir.iterdir():
        chapters_file = novel_dir / "chapters.yaml"
        if chapters_file.exists():
            with open(chapters_file, "r", encoding="utf-8") as f:
                chapters = yaml.safe_load(f) or []
                for ch in chapters:
                    if dimension == "chapter_function":
                        funcs = ch.get("chapter_function", ch.get("chapter_functions", []))
                        used_tags.update(funcs)

    invalid = used_tags - valid_set
    if invalid:
        print(f"维度 {dimension}: 发现 {len(invalid)} 个字典外的标签:")
        for t in invalid:
            print(f"  {t}")
    else:
        print(f"维度 {dimension}: 所有标签均合法")

def suggest_expand(dimension, new_tag):
    """提示用户是否扩展标签字典。"""
    tags_file = TAGS_FILE
    with open(tags_file, "r", encoding="utf-8") as f:
        tags_dict = yaml.safe_load(f) or {}

    dim_data = tags_dict.get(dimension, [])
    if new_tag not in dim_data:
        print(f"\n标签 '{new_tag}' 不在维度 {dimension} 的字典中")
        print(f"如需添加，请手动编辑 {tags_file}")
        print(f"当前 {dimension} 维度有 {len(dim_data)} 个标签值")

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        check_dimension(sys.argv[1])
    else:
        for dim in VALID_DIMENSIONS:
            check_dimension(dim)
