#!/usr/bin/env python
"""人物提取：LLM 从原文提取人物名册、关系网和人物弧线。"""
import os
import sys
import yaml
import json
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

def load_config():
    config_dir = Path("config")
    with open(config_dir / "llm.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def call_llm(system_prompt, user_prompt, config):
    from openai import OpenAI

    client = OpenAI(
        api_key=config["llm"]["api_key"],
        base_url=config["llm"].get("base_url")
    )

    response = client.chat.completions.create(
        model=config["llm"]["model"],
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=config["llm"].get("temperature", 0.3),
        max_tokens=config["llm"].get("max_tokens", 4096),
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)

def generate_characters(material_id):
    """提取人物体系。"""
    novel_dir = Path("data/novels") / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    config = load_config()
    char_dir = novel_dir / "characters"
    char_dir.mkdir(exist_ok=True)
    profiles_dir = char_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    # 读取原文（取前 8000 字）
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        source_text = f.read()[:8000]

    # 读取 meta
    with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    system_prompt = """你是专业的小说人物分析师。请从原文中提取主要人物，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名",
      "role": "protagonist/antagonist/supporting/minor",
      "archetype": "英雄/导师/伙伴/反派/隐士/复仇者/守护者/野心家",
      "moral_spectrum": "善良/灰色/邪恶",
      "description": "角色描述（100字）",
      "arc_summary": "角色弧线概述（50字）",
      "narrative_function": "在故事中的功能",
      "psychology": {
        "fatal_flaw": "致命弱点",
        "obsession": "执念/目标",
        "soft_spot": "软肋",
        "motivation": "驱动力"
      },
      "first_appearance_chapter": 1,
      "key_events": [
        {"chapter": 1, "description": "关键事件描述"}
      ],
      "relationships": [
        {"character": "角色名", "relationship": "关系描述", "nature": "ally/enemy/romance/mentor/rival"}
      ]
    }
  ]
}

注意：
1. 只提取重要人物（不超过 20 人）
2. key_events 只记录关键节点（≤10个）
3. 只提取原文中明确出现的角色
4. 关系描述用中文"""

    user_prompt = f"""请分析以下小说的人物体系：

类型：{meta.get('theme', ['未知'])}

原文摘录（前 8000 字）：
{source_text}

请返回 JSON 格式如上。"""

    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    result = call_llm(system_prompt, user_prompt, config)
    time.sleep(rate_limit)

    characters = result.get("characters", [])

    # 收集所有关系
    all_relationships = []

    # 写入每个人物小传
    for ch in characters:
        profile = {
            "name": ch.get("name"),
            "role": ch.get("role"),
            "archetype": ch.get("archetype"),
            "moral_spectrum": ch.get("moral_spectrum"),
            "description": ch.get("description"),
            "arc_summary": ch.get("arc_summary"),
            "narrative_function": ch.get("narrative_function"),
            "psychology": ch.get("psychology", {}),
            "first_appearance_chapter": ch.get("first_appearance_chapter"),
            "key_events": ch.get("key_events", [])[:10],
            "relationships": ch.get("relationships", [])
        }

        filename = f"{ch['name']}.yaml"
        with open(profiles_dir / filename, "w", encoding="utf-8") as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)

        # 收集关系
        for rel in ch.get("relationships", []):
            all_relationships.append({
                "from": ch.get("name"),
                "to": rel.get("character"),
                "relationship": rel.get("relationship"),
                "nature": rel.get("nature")
            })

    # 写入人物索引
    char_index = {
        "character_count": len(characters),
        "protagonist_count": sum(1 for c in characters if c.get("role") == "protagonist"),
        "antagonist_count": sum(1 for c in characters if c.get("role") == "antagonist"),
        "supporting_count": sum(1 for c in characters if c.get("role") == "supporting"),
        "minor_count": sum(1 for c in characters if c.get("role") == "minor"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    with open(char_dir / "_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(char_index, f, allow_unicode=True, default_flow_style=False)

    # 写入关系网
    with open(char_dir / "relationships.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"relationships": all_relationships}, f, allow_unicode=True, default_flow_style=False)

    print(f"人物提取完成:")
    print(f"  总人物: {char_index['character_count']}")
    print(f"  主角: {char_index['protagonist_count']}")
    print(f"  反派: {char_index['antagonist_count']}")
    print(f"  配角: {char_index['supporting_count']}")
    print(f"  关系: {len(all_relationships)} 条")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_characters.py <material_id>")
        sys.exit(1)

    generate_characters(sys.argv[1])
