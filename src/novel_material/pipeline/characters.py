"""人物提取：分层提取人物体系（核心人物 + 次要人物）。

分层策略：
1. 第一轮：提取主角/反派/重要配角（完整档案：心理分析、弧线、关键事件）
2. 第二轮：补充次要人物（精简档案：基础信息 + 关系）

注意：此脚本在 analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。
"""
import sys
import yaml
import time
from pathlib import Path

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()

_MAX_SUMMARY_TOKENS = 5000


def _build_context(novel_dir: Path, model: str) -> tuple[str, str]:
    """构建分析上下文，优先使用章级摘要池，兜底读原文片段。

    章数 > 200 时自动启用分层均匀采样，确保全书首尾及中间均有代表，
    避免 5000 token 预算仅覆盖超长书前 6-8% 章节的问题。
    """
    chapters_data = load_chapters_data(novel_dir)
    if chapters_data:
        pool = build_summary_pool(chapters_data, _MAX_SUMMARY_TOKENS, model)
        return pool, f"章级摘要池（共 {len(chapters_data)} 章）"

    logger.warning("章节数据不存在或为空，回退到原文前 8000 字（质量受限）")
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        return f.read()[:8000], "原文摘录（前 8000 字）"


def _extract_core_characters(context_text: str, context_label: str, meta: dict, config: dict) -> list:
    """第一轮：提取核心人物（主角/反派/重要配角），完整档案。"""
    system_prompt = """你是专业的小说人物分析师。请提取有完整角色弧线的核心人物，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名",
      "role": "protagonist/antagonist/supporting",
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
1. 只提取有完整弧线的核心人物（主角、反派、重要配角），通常 10-25 人
2. role 只能是 protagonist/antagonist/supporting（不要填写 minor）
3. key_events 只记录关键节点（≤10个）
4. 关系描述用中文"""

    user_prompt = f"""请分析以下小说的核心人物：

类型：{meta.get('theme', ['未知'])}

{context_label}：
{context_text}

请返回 JSON 格式如上，只提取有完整弧线的重要角色。"""

    logger.info("第一轮：提取核心人物...")
    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=8000)
    return result.get("characters", [])


def _extract_minor_characters(
    context_text: str,
    context_label: str,
    meta: dict,
    core_names: list,
    config: dict
) -> list:
    """第二轮：补充次要人物（精简档案）。"""
    system_prompt = """你是专业的小说人物分析师。请补充其他有名字且有剧情作用的次要人物，返回 JSON 格式：
{
  "characters": [
    {
      "name": "角色名",
      "role": "minor",
      "description": "角色描述（50字）",
      "first_appearance_chapter": 1,
      "narrative_function": "在故事中的功能（简述）",
      "relationships": [
        {"character": "角色名", "relationship": "关系描述"}
      ]
    }
  ]
}

注意：
1. 只提取不在已有名单中的次要人物
2. 这些是有名字且有剧情作用但无完整弧线的角色
3. 档案精简，不需要 psychology/arc_summary/archetype 等深层分析
4. 关系描述用中文"""

    user_prompt = f"""请补充以下小说的次要人物：

类型：{meta.get('theme', ['未知'])}

已有核心人物名单（不要重复提取）：
{', '.join(core_names)}

{context_label}：
{context_text}

请返回 JSON 格式如上，补充其他有剧情作用的次要角色。"""

    logger.info("第二轮：补充次要人物...")
    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=8000)
    return result.get("characters", [])


def generate_characters(material_id):
    """分层提取人物体系。

    容错策略：任何轮次失败时使用空数组继续，不中断流程。
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"小说目录不存在: {novel_dir}")
        return

    config = load_config()
    model = config["llm"]["model"]
    char_dir = novel_dir / "characters"
    char_dir.mkdir(exist_ok=True)
    profiles_dir = char_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    # 读取 meta
    with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    # 构建分析上下文
    context_text, context_label = _build_context(novel_dir, model)
    logger.info(f"使用 {context_label} 作为分析基础")

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    # ── 第一轮：核心人物（容错）──
    core_characters = []
    try:
        core_characters = _extract_core_characters(context_text, context_label, meta, config)
        time.sleep(rate_limit)
        logger.info(f"  提取核心人物: {len(core_characters)} 人")
    except Exception as e:
        logger.error(f"核心人物提取失败: {e}")
        logger.warning("使用空列表继续，不中断流程")
        core_characters = []

    core_names = [ch.get("name") for ch in core_characters if ch.get("name")]

    # ── 第二轮：次要人物（容错）──
    minor_characters = []
    try:
        minor_characters = _extract_minor_characters(context_text, context_label, meta, core_names, config)
        time.sleep(rate_limit)
        logger.info(f"  补充次要人物: {len(minor_characters)} 人")
    except Exception as e:
        logger.error(f"次要人物提取失败: {e}")
        logger.warning("使用空列表继续，不中断流程")
        minor_characters = []

    # 合并
    all_characters = core_characters + minor_characters

    # 收集所有关系
    all_relationships = []

    # 写入每个人物小传
    for ch in all_characters:
        role = ch.get("role", "minor")

        # 核心人物完整档案，次要人物精简档案
        if role in ("protagonist", "antagonist", "supporting"):
            profile = {
                "name": ch.get("name"),
                "role": role,
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
        else:
            profile = {
                "name": ch.get("name"),
                "role": "minor",
                "description": ch.get("description"),
                "first_appearance_chapter": ch.get("first_appearance_chapter"),
                "narrative_function": ch.get("narrative_function"),
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
                "nature": rel.get("nature", "unknown")
            })

    # 写入人物索引
    char_index = {
        "character_count": len(all_characters),
        "protagonist_count": sum(1 for c in all_characters if c.get("role") == "protagonist"),
        "antagonist_count": sum(1 for c in all_characters if c.get("role") == "antagonist"),
        "supporting_count": sum(1 for c in all_characters if c.get("role") == "supporting"),
        "minor_count": sum(1 for c in all_characters if c.get("role") == "minor"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    with open(char_dir / "_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(char_index, f, allow_unicode=True, default_flow_style=False)

    # 写入关系网
    with open(char_dir / "relationships.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"relationships": all_relationships}, f, allow_unicode=True, default_flow_style=False)

    logger.info(f"人物提取完成:\n"
                f"  总人物: {char_index['character_count']}\n"
                f"  主角: {char_index['protagonist_count']}\n"
                f"  反派: {char_index['antagonist_count']}\n"
                f"  配角: {char_index['supporting_count']}\n"
                f"  次要: {char_index['minor_count']}\n"
                f"  关系: {len(all_relationships)} 条")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python characters.py <material_id>")
        sys.exit(1)

    generate_characters(sys.argv[1])