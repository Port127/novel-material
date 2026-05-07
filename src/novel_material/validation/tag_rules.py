"""标签合法性校验工具：使用数据库校验标签。"""
import sys

from novel_material.tags.validate import validate_tag, validate_tags_batch, check_dimension_usage
from novel_material.tags.resolve import resolve_tag_domain, suggest_genre_for_tag


def check_dimension(dimension: str) -> None:
    """检查某个维度在已有数据文件中的标签使用情况。"""
    check_dimension_usage(dimension)


def suggest_expand(dimension: str, new_tag: str) -> None:
    """提示用户是否扩展标签字典。"""
    canonical = validate_tag(dimension, new_tag)

    if not canonical:
        print(f"\n标签 '{new_tag}' 不在维度 {dimension} 的字典中")
        print(f"如需添加，请使用:")
        print(f"  nm tags add {dimension} '{new_tag}' common")
        print(f"或运行审核流程:")
        print(f"  nm tags review list")


# 废弃的旧函数（保留向后兼容）

def flatten_tags(dim_data) -> set:
    """【已废弃】递归展开分组 dict 或平铺 list。"""
    print("警告: flatten_tags() 已废弃，请使用 validate_tags_batch()")
    result = set()
    if isinstance(dim_data, list):
        result.update(dim_data)
    elif isinstance(dim_data, dict):
        for v in dim_data.values():
            result.update(flatten_tags(v))
    return result


def build_synonym_reverse(tags_dict: dict) -> dict:
    """【已废弃】从 synonym_map 构建反向映射。"""
    print("警告: build_synonym_reverse() 已废弃，请使用 validate_tag()")
    reverse = {}
    for standard, synonyms in tags_dict.get("synonym_map", {}).items():
        if isinstance(synonyms, list):
            for syn in synonyms:
                reverse[syn] = standard
    return reverse


def synonym_expand(tag: str, reverse_map: dict) -> str:
    """【已废弃】将同义词映射为标准名称。"""
    print("警告: synonym_expand() 已废弃，请使用 validate_tag()")
    return reverse_map.get(tag, tag)


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        check_dimension(sys.argv[1])
    else:
        for dim in ["element", "style", "setting", "structure"]:
            check_dimension(dim)