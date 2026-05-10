"""人物提取：分层提取人物体系（核心人物 + 次要人物）。

分层策略：
1. 统计章节出场人物频率，生成候选名单
2. 第一轮：提取主角/反派/重要配角（完整档案：心理分析、弧线、关键事件）
3. 第二轮：补充次要人物（精简档案：基础信息 + 关系）

注意：此脚本在 analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。
"""
import sys
import yaml
import time
import re
from pathlib import Path
from collections import Counter
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm, get_last_call_finish_reason
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()

# 有效角色类型
VALID_ROLES = ("protagonist", "antagonist", "supporting", "minor")


# ============================================================
# 增量写入辅助函数（断点续传支持）
# ============================================================

def _save_character_profile(profiles_dir: Path, idx: int, profile: dict, name: str) -> None:
    """保存单个人物小传到独立文件（增量写入）。

    Args:
        profiles_dir: profiles 目录路径
        idx: 人物序号
        profile: 人物档案数据
        name: 人物名称（用于生成文件名）
    """
    # slug 化文件名：只保留字母、数字、中文，其他替换为下划线
    slug = re.sub(r'[^\w一-鿿]', '_', name)
    filename = f"{slug}_{idx:03d}.yaml"
    with open(profiles_dir / filename, "w", encoding="utf-8") as f:
        yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)


def _load_existing_profiles(char_dir: Path) -> tuple[list, set]:
    """加载已保存的人物小传（断点续传）。

    Args:
        char_dir: characters 目录路径

    Returns:
        tuple: (已保存的人物档案列表, 已保存的人物名称集合)
    """
    profiles_dir = char_dir / "profiles"
    if not profiles_dir.exists():
        return [], set()

    existing_profiles = []
    existing_names = set()

    for f in profiles_dir.glob("*.yaml"):
        try:
            profile = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            if profile.get("name"):
                existing_profiles.append(profile)
                existing_names.add(profile["name"])
        except Exception:
            continue

    return existing_profiles, existing_names


def _build_profile_from_character(ch: dict, role: str) -> dict:
    """根据角色类型构建人物档案。

    Args:
        ch: LLM 返回的人物数据
        role: 角色类型

    Returns:
        dict: 人物档案
    """
    if role in ("protagonist", "antagonist", "supporting"):
        return {
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
        return {
            "name": ch.get("name"),
            "role": "minor",
            "description": ch.get("description"),
            "first_appearance_chapter": ch.get("first_appearance_chapter"),
            "narrative_function": ch.get("narrative_function"),
            "relationships": ch.get("relationships", [])
        }


def _extract_appearance_stats(chapters_data: list) -> dict:
    """统计章节出场人物频率。

    特殊类型章节（afterword/author_note）不参与统计。

    返回：
        dict: {人物名: 出场章数}
    """
    all_chars = []
    for ch in chapters_data:
        ch_type = ch.get("type", "normal")
        # 跳过特殊类型章节
        if ch_type in ("afterword", "author_note"):
            continue
        chars = ch.get("characters_appear", [])
        all_chars.extend(chars)
    return dict(Counter(all_chars))


def _build_context(novel_dir: Path, config: dict, chapters_data: list | None = None, material_id: str = "") -> tuple[str, str]:
    """构建分析上下文，优先使用章级摘要池，兜底读原文片段。

    章数 > 200 时自动启用分层均匀采样，确保全书首尾及中间均有代表。
    特殊类型章节（afterword/author_note）不参与摘要池构建。

    Args:
        novel_dir: 小说目录
        config: 配置字典
        chapters_data: 可选的已加载章节数据（避免重复调用 load_chapters_data）
    """
    model = config["llm"]["model"]
    if chapters_data is None:
        chapters_data = load_chapters_data(novel_dir)
    if chapters_data:
        # 过滤特殊类型章节（afterword/author_note 不参与人物分析）
        filtered_chapters = [
            ch for ch in chapters_data
            if ch.get("type", "normal") in ("normal", "extra")
        ]
        skipped_count = len(chapters_data) - len(filtered_chapters)

        pool = build_summary_pool(filtered_chapters, config["llm"]["characters_summary_tokens"], model)
        return pool, f"章级摘要池（共 {len(filtered_chapters)} 章，跳过 {skipped_count} 章特殊类型）"

    prefix = f"[{material_id}] " if material_id else ""
    logger.warning(f"{prefix}章节数据不存在或为空，回退到原文前 8000 字（质量受限）")
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        return f.read()[:8000], "原文摘录（前 8000 字）"


def _extract_core_characters(
    context_text: str,
    context_label: str,
    meta: dict,
    appearance_stats: dict,
    config: dict,
    material_id: str = "",
) -> list:
    """第一轮：提取核心人物（主角/反派/重要配角），完整档案。"""
    prefix = f"[{material_id}] " if material_id else ""
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
3. key_events 按重要性排序（最重要的在前），最多 10 个
4. 关系描述用中文"""

    # 构建出场统计文本（高频人物优先）
    sorted_chars = sorted(appearance_stats.items(), key=lambda x: -x[1])
    stats_lines = []
    for name, count in sorted_chars[:100]:  # 只展示前 100 个高频人物
        stats_lines.append(f"  {name}: {count} 章")
    stats_text = "\n".join(stats_lines)

    user_prompt = f"""请分析以下小说的核心人物：

类型：{meta.get('theme', ['未知'])}

【出场人物统计】（按出场频率排序，前100名）：
{stats_text}

{context_label}：
{context_text}

请返回 JSON 格式如上，只提取有完整弧线的重要角色。
优先关注出场频率高的人物，但也要考虑其剧情重要性而非仅看数量。"""

    logger.info(f"{prefix}第一轮：提取核心人物...")
    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=8000, timeout_override=config["llm"]["characters_timeout"], context=f"{material_id} 人物#核心")
    # 兼容 LLM 直接返回数组的情况
    if isinstance(result, list):
        logger.warning(f"{prefix}人物提取返回裸数组，自动适配")
        characters = result
    else:
        characters = result.get("characters", [])
    logger.info(f"{prefix}核心人物提取完成: {len(characters)} 人 | finish={get_last_call_finish_reason()}")
    return characters


def _extract_minor_characters(
    context_text: str,
    context_label: str,
    meta: dict,
    core_names: list,
    appearance_stats: dict,
    config: dict,
    material_id: str = "",
) -> list:
    """第二轮：补充次要人物（精简档案）。"""
    prefix = f"[{material_id}] " if material_id else ""
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

    # 构建出场统计文本（排除已提取的核心人物）
    remaining_chars = {
        name: count for name, count in appearance_stats.items()
        if name not in core_names
    }
    sorted_remaining = sorted(remaining_chars.items(), key=lambda x: -x[1])
    stats_lines = []
    for name, count in sorted_remaining[:100]:
        stats_lines.append(f"  {name}: {count} 章")
    stats_text = "\n".join(stats_lines)

    user_prompt = f"""请补充以下小说的次要人物：

类型：{meta.get('theme', ['未知'])}

已有核心人物名单（不要重复提取）：
{', '.join(core_names)}

【剩余出场人物统计】（按出场频率排序，前100名）：
{stats_text}

{context_label}：
{context_text}

请返回 JSON 格式如上，补充其他有剧情作用的次要角色。
优先关注出场频率较高（≥5章）的人物，但也要判断其是否有实际剧情作用。"""

    logger.info(f"{prefix}第二轮：补充次要人物...")
    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=8000, timeout_override=config["llm"]["characters_timeout"], context=f"{material_id} 人物#次要")
    # 兼容 LLM 直接返回数组的情况
    if isinstance(result, list):
        logger.warning(f"{prefix}次要人物提取返回裸数组，自动适配")
        characters = result
    else:
        characters = result.get("characters", [])
    logger.info(f"{prefix}次要人物提取完成: {len(characters)} 人 | finish={get_last_call_finish_reason()}")
    return characters


def generate_characters(material_id, progress_callback: Callable[[int, int, str], None] | None = None, provider: str | None = None) -> bool:
    """分层提取人物体系。

    容错策略：任何轮次失败时使用空数组继续，不中断流程。
    返回 True 表示成功。

    参数：
        material_id: 素材 ID
        progress_callback: 可选进度回调函数 (done: int, total: int, desc: str) -> None
        provider: 服务商名称（可选，不指定则使用默认配置）
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    config = load_config(provider)
    char_dir = novel_dir / "characters"
    char_dir.mkdir(exist_ok=True)
    profiles_dir = char_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    # 读取 meta
    with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "?")

    # 读取章节索引获取章数
    chapter_index_file = novel_dir / "chapter_index.yaml"
    chapter_count = 0
    if chapter_index_file.exists():
        with open(chapter_index_file, "r", encoding="utf-8") as f:
            chapter_index = yaml.safe_load(f) or []
            chapter_count = len(chapter_index)

    # 输出小说基本信息
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")

    # 加载章节数据并统计出场人物
    chapters_data = load_chapters_data(novel_dir)
    appearance_stats = _extract_appearance_stats(chapters_data) if chapters_data else {}
    logger.info(f"[{material_id}] 出场人物统计: {len(appearance_stats)} 个不同人物")

    # 构建分析上下文（传递已加载的 chapters_data，避免重复调用）
    context_text, context_label = _build_context(novel_dir, config, chapters_data, material_id=material_id)
    context_chars = len(context_text)
    logger.info(f"[{material_id}] 输入: {context_chars} 字符 | {context_label}")

    # 加载已保存的人物（断点续传）
    existing_profiles, existing_names = _load_existing_profiles(char_dir)
    if existing_profiles:
        logger.info(f"[{material_id}] 断点续传：已保存 {len(existing_profiles)} 个人物")

    # 收集所有关系（后续去重）
    all_relationships = []

    # 收集已有人物的关系（断点续传时避免关系丢失）
    for profile in existing_profiles:
        profile_name = profile.get("name")
        if not profile_name:
            continue
        for rel in profile.get("relationships", []):
            all_relationships.append({
                "from": profile_name,
                "to": rel.get("character"),
                "relationship": rel.get("relationship"),
                "nature": rel.get("nature", "unknown")
            })

    # ── 第一轮：核心人物（容错，增量写入）──
    core_characters = []
    new_core_count = 0
    try:
        if progress_callback:
            progress_callback(0, 2, "提取核心人物")
        core_characters = _extract_core_characters(context_text, context_label, meta, appearance_stats, config, material_id=material_id)
        if progress_callback:
            progress_callback(1, 2, f"核心人物: {len(core_characters)} 人")
        else:
            logger.info(f"[{material_id}] 提取核心人物: {len(core_characters)} 人")
    except Exception as e:
        logger.error(f"[{material_id}] 核心人物提取失败: {e}")
        logger.warning(f"[{material_id}] 使用空列表继续，不中断流程")
        core_characters = []

    # 核心人物立即保存（增量写入）
    idx = len(existing_profiles)
    for ch in core_characters:
        name = ch.get("name")
        if not name or name in existing_names:
            continue  # 断点续传：跳过已存在的人物

        # 验证 role 字段
        role = ch.get("role", "supporting")
        if role not in VALID_ROLES:
            logger.warning(f"[{material_id}] 无效 role '{role}'，默认为 supporting")
            role = "supporting"

        profile = _build_profile_from_character(ch, role)
        _save_character_profile(profiles_dir, idx, profile, name)
        existing_profiles.append(profile)
        existing_names.add(name)
        idx += 1
        new_core_count += 1

        # 收集关系
        for rel in ch.get("relationships", []):
            all_relationships.append({
                "from": name,
                "to": rel.get("character"),
                "relationship": rel.get("relationship"),
                "nature": rel.get("nature", "unknown")
            })

    if new_core_count > 0:
        logger.info(f"[{material_id}] 已保存 {new_core_count} 个核心人物")

    core_names = [ch.get("name") for ch in core_characters if ch.get("name")]

    # ── 第二轮：次要人物（容错，增量写入）──
    minor_characters = []
    new_minor_count = 0
    try:
        if progress_callback:
            progress_callback(1, 2, "补充次要人物")
        minor_characters = _extract_minor_characters(context_text, context_label, meta, core_names, appearance_stats, config, material_id=material_id)
        if progress_callback:
            progress_callback(2, 2, f"次要人物: {len(minor_characters)} 人")
        else:
            logger.info(f"[{material_id}] 补充次要人物: {len(minor_characters)} 人")
    except Exception as e:
        logger.error(f"[{material_id}] 次要人物提取失败: {e}")
        logger.warning(f"[{material_id}] 使用空列表继续，不中断流程")
        minor_characters = []

    # 次要人物立即保存（增量写入）
    for ch in minor_characters:
        name = ch.get("name")
        if not name or name in existing_names:
            continue  # 断点续传：跳过已存在的人物

        profile = _build_profile_from_character(ch, "minor")
        _save_character_profile(profiles_dir, idx, profile, name)
        existing_profiles.append(profile)
        existing_names.add(name)
        idx += 1
        new_minor_count += 1

        # 收集关系
        for rel in ch.get("relationships", []):
            all_relationships.append({
                "from": name,
                "to": rel.get("character"),
                "relationship": rel.get("relationship"),
                "nature": rel.get("nature", "unknown")
            })

    if new_minor_count > 0:
        logger.info(f"[{material_id}] 已保存 {new_minor_count} 个次要人物")

    # 合并所有人物（现有 + 新增）
    all_characters = existing_profiles

    # 关系去重：按人物对去重（A-B 和 B-A 视为同一对）
    seen_pairs = set()
    unique_relationships = []
    for rel in all_relationships:
        pair_key = tuple(sorted([rel["from"], rel["to"]]))
        if pair_key not in seen_pairs:
            seen_pairs.add(pair_key)
            unique_relationships.append(rel)

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
        yaml.dump({"relationships": unique_relationships}, f, allow_unicode=True, default_flow_style=False)

    logger.info(
        f"[{material_id}] 人物提取完成:\n"
        f"  总人物: {char_index['character_count']}\n"
        f"  主角: {char_index['protagonist_count']}\n"
        f"  反派: {char_index['antagonist_count']}\n"
        f"  配角: {char_index['supporting_count']}\n"
        f"  次要: {char_index['minor_count']}\n"
        f"  关系: {len(unique_relationships)} 条"
    )

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python characters.py <material_id>")
        sys.exit(1)

    generate_characters(sys.argv[1])