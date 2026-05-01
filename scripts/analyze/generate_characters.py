#!/usr/bin/env python
"""人物提取：LLM 基于章级摘要池提取人物名册、关系网和人物弧线。

注意：此脚本在 chapter_analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。
"""
import sys
import yaml
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from scripts.core.paths import NOVELS_DIR
from scripts.core.llm_client import load_config, call_llm, truncate_to_tokens

_MAX_SUMMARY_TOKENS = 5000


def _build_context(novel_dir: Path, model: str) -> tuple[str, str]:
    """构建分析上下文，优先使用章级摘要池，兜底读原文片段。"""
    chapters_file = novel_dir / "chapters.yaml"
    if chapters_file.exists():
        chapters_data = yaml.safe_load(chapters_file.read_text(encoding="utf-8")) or []
        if chapters_data:
            lines = []
            for ch in chapters_data:
                summary = ch.get("summary", "")
                if summary:
                    lines.append(f"第{ch.get('chapter', '?')}章《{ch.get('title', '')}》：{summary}")
            if lines:
                pool = truncate_to_tokens("\n".join(lines), _MAX_SUMMARY_TOKENS, model=model)
                return pool, f"章级摘要池（共 {len(chapters_data)} 章）"

    print("警告: chapters.yaml 不存在或为空，回退到原文前 8000 字（质量受限）")
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        return f.read()[:8000], "原文摘录（前 8000 字）"


def generate_characters(material_id):
    """提取人物体系。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    config = load_config()
    model = config["llm"]["model"]
    char_dir = novel_dir / "characters"
    char_dir.mkdir(exist_ok=True)
    profiles_dir = char_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    # 读取 meta
    with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    # 构建分析上下文（章级摘要池 > 原文片段）
    context_text, context_label = _build_context(novel_dir, model)
    print(f"使用 {context_label} 作为分析基础")

    system_prompt = """你是专业的小说人物分析师。请根据提供的内容提取主要人物，返回 JSON 格式：
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

{context_label}：
{context_text}

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
