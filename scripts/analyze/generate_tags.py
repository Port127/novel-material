#!/usr/bin/env python
"""标签生成：LLM 为整部小说生成宏观标签（类型/基调/叙事结构/风格/长板/套路识别）。"""
import sys
import yaml
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from scripts.core.paths import NOVELS_DIR, TAGS_FILE
from scripts.core.llm_client import load_config, call_llm
from scripts.utils.tag_validator import flatten_tags, build_synonym_reverse, synonym_expand

def load_tags_dict():
    if TAGS_FILE.exists():
        with open(TAGS_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def generate_tags(material_id):
    """为整部小说生成多维标签。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    config = load_config()
    tags_dict = load_tags_dict()

    # 读取原文（取前 5000 字）
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        source_text = f.read()[:5000]

    # 读取 meta 和大纲
    with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    # 如果有 outline，读取结构信息辅助标签生成
    outline_index_file = novel_dir / "outline" / "_index.yaml"
    structure_info = ""
    if outline_index_file.exists():
        with open(outline_index_file, "r", encoding="utf-8") as f:
            outline_index = yaml.safe_load(f) or {}
        structure_info = f"结构类型：{outline_index.get('structure_type', '未知')}"

    # 从 tags_dict 中提取各维度标签（递归展开分组 dict）
    valid_channels = tags_dict.get("channel", [])

    # genre: 一级 key 列表
    valid_genres_primary = list(tags_dict.get("genre", {}).keys())
    # genre: 所有二级值
    valid_genres_secondary = []
    for sub in tags_dict.get("genre", {}).values():
        if isinstance(sub, list):
            valid_genres_secondary.extend(sub)

    # element 分组展示（保留分组信息）
    element_groups = tags_dict.get("element", {})
    valid_elements = flatten_tags(element_groups)

    # 其他维度平铺展开
    valid_styles = flatten_tags(tags_dict.get("style", {}))
    valid_structures = flatten_tags(tags_dict.get("structure", {}))
    valid_settings = flatten_tags(tags_dict.get("setting", {}))

    # 构建同义词反向映射
    reverse_map = build_synonym_reverse(tags_dict)

    # 元素标签分组展示字符串（按组展示）
    element_prompt_parts = []
    if isinstance(element_groups, dict):
        for group_name, group_tags in element_groups.items():
            if isinstance(group_tags, list) and group_tags:
                element_prompt_parts.append(f"  《{group_name}》: {', '.join(group_tags[:15])}…")
    element_prompt_str = "\n".join(element_prompt_parts) if element_prompt_parts else ", ".join(list(valid_elements)[:30])

    # 风格标签分组展示字符串
    style_groups = tags_dict.get("style", {})
    style_prompt_parts = []
    if isinstance(style_groups, dict):
        for group_name, group_tags in style_groups.items():
            if isinstance(group_tags, list) and group_tags:
                style_prompt_parts.append(f"  《{group_name}》: {', '.join(group_tags[:10])}…")
    style_prompt_str = "\n".join(style_prompt_parts) if style_prompt_parts else ", ".join(list(valid_styles)[:20])

    system_prompt = f"""你是专业的小说标签标注师。请为小说生成以下多维标签：
{{
  "channel": "频道（必选 1 个）：{valid_channels}",
  "genre_primary": "主题材（必选，从下列一级题材中选 1 个）：{valid_genres_primary}",
  "genre_secondary": ["次题材（最多 2 个，从下列二级题材中选）：{valid_genres_secondary[:30]}…"],
  "elements": ["元素标签（选 3-8 个，必须从以下分组中选取）:\n{element_prompt_str}"],
  "style": ["风格标签（选 1-3 个，必须从以下分组中选取）:\n{style_prompt_str}"],
  "structure": "叙事结构（从下列选 1 个）：{list(valid_structures)[:15]}",
  "setting": "世界观力量体系（从下列选 1 个）：{list(valid_settings)[:15]}",
  "hooks": ["长板/亮点（1-3 个，自由填写）"],
  "tropes": ["套路识别（1-3 个，自由填写）"],
  "themes": ["主题（1-3 个，自由填写）"]
}}

注意：
1. channel/genre_primary/genre_secondary/style/structure/setting 必须从上面提供的字典中选取
2. elements 必须从上面分组列表中选取 3-8 个，不得编造
3. hooks/tropes/themes 可以自由填写
4. 不要编造不在字典中的标签值"""

    user_prompt = f"""请为以下小说生成标签：

{meta.get('premise', 'N/A')}
{structure_info}

原文摘录：
{source_text}

请返回 JSON 格式如上。"""

    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    result = call_llm(system_prompt, user_prompt, config)
    time.sleep(rate_limit)

    # 校验标签合法性（先同义词展开再判断）
    tags = {}
    for key in ["channel", "genre_primary", "genre_secondary", "elements", "style", "structure", "setting", "hooks", "tropes", "themes"]:
        value = result.get(key, [] if key not in ["channel", "genre_primary", "structure", "setting"] else "")
        if isinstance(value, str) and value:
            valid_set: set = set()
            if key == "channel":
                valid_set = set(valid_channels)
            elif key == "genre_primary":
                valid_set = set(valid_genres_primary)
            elif key == "structure":
                valid_set = valid_structures
            elif key == "setting":
                valid_set = valid_settings

            if valid_set:
                canonical = synonym_expand(value, reverse_map)
                if canonical not in valid_set:
                    print(f"警告: 标签 '{key}' 的值 '{value}' 不在字典中，跳过")
                    continue
                value = canonical  # 统一为标准名称

        elif isinstance(value, list):
            valid_set = set()
            if key == "elements":
                valid_set = valid_elements
            elif key == "style":
                valid_set = valid_styles
            elif key == "genre_secondary":
                valid_set = set(valid_genres_secondary)

            if valid_set:
                filtered = []
                for v in value:
                    canonical = synonym_expand(str(v), reverse_map)
                    if canonical in valid_set:
                        filtered.append(canonical)
                    else:
                        print(f"警告: 标签 '{key}' 中的 '{v}' 不在字典中，已过滤")
                value = filtered

        tags[key] = value

    # 写入 tags.yaml
    with open(novel_dir / "tags.yaml", "w", encoding="utf-8") as f:
        yaml.dump(tags, f, allow_unicode=True, default_flow_style=False)

    # 更新 meta.yaml 中的 genre 和 tags
    if "genre_primary" in tags:
        genres = [tags["genre_primary"]]
        if isinstance(tags.get("genre_secondary"), list):
            genres.extend(tags["genre_secondary"])
        meta["genre"] = genres

    meta["tags"] = tags

    with open(novel_dir / "meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    print(f"标签生成完成:")
    print(f"  频道: {tags.get('channel')}")
    print(f"  类型: {tags.get('genre_primary')}")
    print(f"  元素: {len(tags.get('elements', []))} 个")
    print(f"  风格: {tags.get('style')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_tags.py <material_id>")
        sys.exit(1)

    generate_tags(sys.argv[1])
