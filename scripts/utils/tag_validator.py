#!/usr/bin/env python
"""标签合法性校验工具：检查各维度标签是否在字典范围内。

支持功能：
- flatten_tags()：递归展开分组 dict/list 为平铺集合
- synonym_expand()：将同义词映射到标准名称
- check_dimension()：按维度扫描已有数据文件，报告字典外标签
"""
import sys
import yaml
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.core.paths import NOVELS_DIR, TAGS_FILE

# 已知维度列表（与 tags.yaml 的顶级 key 对应）
VALID_DIMENSIONS = [
    "channel",           # L0 频道
    "genre",             # L1-L2 题材
    "element",           # L3 元素
    "character_archetype",  # 角色（修复：原为 "character"）
    "style",             # 风格
    "structure",         # 结构
    "setting",           # 世界观
    "chapter_function",  # 章节功能
]


def load_tags_dict() -> dict:
    """加载全局标签字典。"""
    if not TAGS_FILE.exists():
        print("错误: 标签字典不存在")
        return {}
    with open(TAGS_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def flatten_tags(dim_data) -> set:
    """递归展开分组 dict 或平铺 list，返回所有标签值的集合（不含分组 key）。"""
    result = set()
    if isinstance(dim_data, list):
        result.update(dim_data)
    elif isinstance(dim_data, dict):
        for v in dim_data.values():
            result.update(flatten_tags(v))
    return result


def build_synonym_reverse(tags_dict: dict) -> dict:
    """从 synonym_map 构建反向映射：同义词 → 标准名称。"""
    reverse = {}
    for standard, synonyms in tags_dict.get("synonym_map", {}).items():
        if isinstance(synonyms, list):
            for syn in synonyms:
                reverse[syn] = standard
    return reverse


def synonym_expand(tag: str, reverse_map: dict) -> str:
    """将同义词映射为标准名称，找不到则原样返回。"""
    return reverse_map.get(tag, tag)


def check_dimension(dimension: str) -> None:
    """检查某个维度在已有数据文件中的标签使用情况。"""
    tags_dict = load_tags_dict()
    if not tags_dict:
        return

    valid_set = flatten_tags(tags_dict.get(dimension, {}))
    reverse_map = build_synonym_reverse(tags_dict)
    used_tags: set = set()

    for novel_dir in NOVELS_DIR.iterdir():
        if not novel_dir.is_dir():
            continue

        if dimension == "chapter_function":
            # 扫 chapters.yaml
            chapters_file = novel_dir / "chapters.yaml"
            if chapters_file.exists():
                chapters = yaml.safe_load(chapters_file.read_text(encoding="utf-8")) or []
                for ch in chapters:
                    if not isinstance(ch, dict):
                        continue
                    funcs = ch.get("chapter_function", ch.get("chapter_functions", []))
                    used_tags.update(funcs or [])

        elif dimension == "character_archetype":
            # 扫 characters.yaml（角色原型存在此文件）
            chars_file = novel_dir / "characters.yaml"
            if chars_file.exists():
                chars_data = yaml.safe_load(chars_file.read_text(encoding="utf-8")) or {}
                chars_list = chars_data.get("characters", [])
                for ch in chars_list:
                    if not isinstance(ch, dict):
                        continue
                    archetype = ch.get("archetype")
                    if archetype:
                        used_tags.add(archetype)
                    role = ch.get("role")
                    if role:
                        used_tags.add(role)

        elif dimension in ("element", "style", "structure", "setting"):
            # 扫小说级 tags.yaml
            novel_tags_file = novel_dir / "tags.yaml"
            if novel_tags_file.exists():
                novel_tags = yaml.safe_load(novel_tags_file.read_text(encoding="utf-8")) or {}
                # element → elements 字段
                field_map = {
                    "element": "elements",
                    "style": "style",
                    "structure": "structure",
                    "setting": "setting",
                }
                field = field_map.get(dimension, dimension)
                val = novel_tags.get(field, [])
                if isinstance(val, list):
                    used_tags.update(val)
                elif isinstance(val, str):
                    used_tags.add(val)

    # 同义词展开后再判断合法性
    invalid = set()
    for tag in used_tags:
        canonical = synonym_expand(tag, reverse_map)
        if canonical not in valid_set:
            invalid.add(tag)

    if invalid:
        print(f"维度 {dimension}: 发现 {len(invalid)} 个字典外的标签:")
        for t in sorted(invalid):
            print(f"  {t}")
    else:
        print(f"维度 {dimension}: 所有标签均合法 (已用 {len(used_tags)} 个)")


def suggest_expand(dimension: str, new_tag: str) -> None:
    """提示用户是否扩展标签字典。"""
    tags_dict = load_tags_dict()
    valid_set = flatten_tags(tags_dict.get(dimension, {}))
    if new_tag not in valid_set:
        print(f"\n标签 '{new_tag}' 不在维度 {dimension} 的字典中")
        print(f"如需添加，请手动编辑 {TAGS_FILE}")
        print(f"当前 {dimension} 维度有 {len(valid_set)} 个标签值")


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        check_dimension(sys.argv[1])
    else:
        for dim in VALID_DIMENSIONS:
            check_dimension(dim)
