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

    # 从 tags_dict 中提取合法标签值列表
    valid_channels = tags_dict.get("channel", [])
    valid_genres = []
    for genre_data in tags_dict.get("genre", {}).values():
        if isinstance(genre_data, list):
            valid_genres.extend(genre_data)
    valid_elements = tags_dict.get("element", [])
    valid_styles = tags_dict.get("style", [])
    valid_structures = tags_dict.get("structure", [])
    valid_settings = tags_dict.get("setting", [])

    system_prompt = f"""你是专业的小说标签标注师。请为小说生成以下多维标签：
{{
  "channel": "频道：{valid_channels}",
  "genre_primary": "主类型（从下面选）",
  "genre_secondary": ["次类型（最多2个）"],
  "elements": ["元素标签（3-8个）：{valid_elements}"],
  "style": ["风格标签（1-3个）：{valid_styles}"],
  "structure": "叙事结构（从下面选）：{valid_structures}",
  "setting": "世界观设定类型（从下面选）：{valid_settings}",
  "hooks": ["长板/亮点（1-3个，自由填写）"],
  "tropes": ["套路识别（1-3个，自由填写）"],
  "themes": ["主题（1-3个，自由填写）"]
}}

注意：
1. channel/genre/style/structure/setting 必须从提供的标签字典中选取
2. elements 必须从元素标签中选取 3-8 个
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

    # 校验标签合法性
    tags = {}
    for key in ["channel", "genre_primary", "genre_secondary", "elements", "style", "structure", "setting", "hooks", "tropes", "themes"]:
        value = result.get(key, [] if key not in ["channel", "genre_primary", "structure", "setting"] else "")
        if isinstance(value, str):
            # 检查是否在合法标签中
            valid_set = set()
            if key == "channel":
                valid_set = set(valid_channels)
            elif key == "genre_primary":
                valid_set = set(valid_genres)
            elif key == "style":
                valid_set = set(valid_styles)
            elif key == "structure":
                valid_set = set(valid_structures)
            elif key == "setting":
                valid_set = set(valid_settings)

            if value and value not in valid_set:
                print(f"警告: 标签 '{key}' 的值 '{value}' 不在字典中，跳过")
                continue
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
