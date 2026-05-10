"""世界观提取：LLM 基于章级摘要池提取世界观设定（力量体系/地理/势力/背景知识）。

注意：此脚本在 analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。

轻量优化：
- 从章级分析的 setting 字段聚合地点统计
- 从 characters_appear 中识别组织名（如"XX成员"、"XX学生")
- 传入聚合统计给 LLM，增强提取准确性
"""
import sys
import yaml
import time
import re
from pathlib import Path
from collections import Counter

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm, get_last_call_finish_reason
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()


# 组织名匹配模式（用于从 characters_appear 中提取组织）
ORGANIZATION_PATTERNS = [
    r"(.+)成员$",      # XX成员
    r"(.+)学生$",      # XX学生
    r"(.+)弟子$",      # XX弟子
    r"(.+)士兵$",      # XX士兵
    r"(.+)队员$",      # XX队员
    r"(.+)学员$",      # XX学员
]


def _aggregate_worldbuilding_stats(chapters_data: list) -> dict:
    """从章级分析中聚合组织/地点统计。

    Args:
        chapters_data: 章节数据列表

    Returns:
        dict: {
            "organizations": {"组织名": 出场章数},
            "locations": {"地点名": 出场章数}
        }
    """
    org_counts = Counter()
    location_counts = Counter()

    for ch in chapters_data:
        # 跳过特殊类型章节
        ch_type = ch.get("type", "normal")
        if ch_type in ("afterword", "author_note"):
            continue

        # 从 characters_appear 中识别组织名
        chars = ch.get("characters_appear", [])
        for char_name in chars:
            for pattern in ORGANIZATION_PATTERNS:
                match = re.match(pattern, char_name)
                if match:
                    org_name = match.group(1)
                    org_counts[org_name] += 1
                    break

        # 从 setting 中聚合地点
        settings = ch.get("setting", [])
        for setting in settings:
            # 清理地点名（去掉"XX场景"、"XX环境"等后缀）
            clean_setting = setting
            for suffix in ["场景", "环境", "地带", "区域"]:
                if setting.endswith(suffix) and len(setting) > len(suffix):
                    clean_setting = setting[:-len(suffix)]
            location_counts[clean_setting] += 1

    return {
        "organizations": dict(org_counts.most_common(30)),
        "locations": dict(location_counts.most_common(30))
    }


def _build_context(novel_dir: Path, config: dict, chapters_data: list | None = None, material_id: str = "") -> tuple[str, str]:
    """构建分析上下文，优先使用章级摘要池，兜底读原文片段。

    章数 > 200 时自动启用分层均匀采样，确保全书首尾及中间均有代表。
    特殊类型章节（afterword/author_note）不参与摘要池构建。

    Args:
        novel_dir: 小说目录
        config: LLM配置
        chapters_data: 可选的已加载章节数据（避免重复调用 load_chapters_data）
        material_id: 素材ID
    """
    model = config["llm"]["model"]
    if chapters_data is None:
        chapters_data = load_chapters_data(novel_dir)
    if chapters_data:
        # 过滤特殊类型章节
        filtered_chapters = [
            ch for ch in chapters_data
            if ch.get("type", "normal") in ("normal", "extra")
        ]
        skipped_count = len(chapters_data) - len(filtered_chapters)

        pool = build_summary_pool(filtered_chapters, config["llm"]["worldbuilding_summary_tokens"], model)
        return pool, f"章级摘要池（共 {len(filtered_chapters)} 章，跳过 {skipped_count} 章特殊类型）"

    prefix = f"[{material_id}] " if material_id else ""
    logger.warning(f"{prefix}章节数据不存在或为空，回退到原文前 10000 字（质量受限）")
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        return f.read()[:10000], "原文摘录（前 10000 字）"


def generate_worldbuilding(material_id, provider: str | None = None) -> bool:
    """提取世界观设定。

    容错策略：LLM 失败时生成空结构，不中断流程。
    返回 True 表示成功。

    参数：
        material_id: 素材 ID
        provider: 服务商名称（可选，不指定则使用默认配置）
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    config = load_config(provider)
    wb_dir = novel_dir / "worldbuilding"
    wb_dir.mkdir(exist_ok=True)

    # 读取 meta
    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
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

    # 加载章节数据并聚合统计（新增）
    chapters_data = load_chapters_data(novel_dir)
    wb_stats = _aggregate_worldbuilding_stats(chapters_data) if chapters_data else {}
    org_stats = wb_stats.get("organizations", {})
    loc_stats = wb_stats.get("locations", {})
    logger.info(
        f"[{material_id}] 聚合统计: {len(org_stats)} 个组织候选, {len(loc_stats)} 个地点候选"
    )

    # 构建分析上下文（章级摘要池 > 原文片段，传入已加载的 chapters_data）
    context_text, context_label = _build_context(novel_dir, config, chapters_data, material_id=material_id)
    context_chars = len(context_text)
    logger.info(f"[{material_id}] 输入: {context_chars} 字符 | {context_label}")

    # 构建统计信息文本（新增）
    org_text = ""
    if org_stats:
        org_lines = [f"  {name}: {count} 章提及" for name, count in org_stats.items()]
        org_text = "\n【组织出现频率】（从章级分析聚合）:\n" + "\n".join(org_lines)

    loc_text = ""
    if loc_stats:
        loc_lines = [f"  {name}: {count} 章出现" for name, count in loc_stats.items()]
        loc_text = "\n【地点出现频率】（从章级分析聚合）:\n" + "\n".join(loc_lines)

    stats_context = org_text + loc_text

    system_prompt = """你是专业的小说世界观分析师。请根据提供的内容提取以下世界观设定，返回 JSON 格式：
{
  "power_system": {
    "name": "体系名称",
    "description": "体系概述",
    "levels": [
      {"name": "境界/等级名", "description": "特征描述", "abilities": ["能力1"]}
    ],
    "rules": ["规则1", "规则2"]
  },
  "geography": {
    "world_name": "世界名称",
    "regions": [
      {"name": "地名", "description": "描述", "importance": "primary/secondary/minor", "notable_features": ["特征"]}
    ],
    "spatial_rules": ["空间规则"]
  },
  "factions": [
    {"name": "势力名", "type": "宗门/帝国/家族/组织", "description": "描述", "leader": "领袖", "strength": "实力等级", "allies": ["盟友"], "enemies": ["敌人"], "importance": "primary/secondary/minor"}
  ],
  "lore": {
    "history": ["历史事件"],
    "myths": ["神话传说"],
    "taboos": ["禁忌"],
    "cultural_notes": ["文化特点"]
  }
}

注意：
1. 所有名称和描述用中文
2. 如果某个维度不存在，留空数组
3. importance 标注重要性（高频出现的组织/地点应为 primary）
4. 只提取原文中明确提到的内容，不要编造
5. 组织出现频率列表中的组织应优先提取，补充详细信息"""

    user_prompt = f"""请分析以下小说的世界观设定：

类型：{meta.get('theme', ['未知'])}
基调：{meta.get('tone', ['未知'])}
{stats_context}

{context_label}：
{context_text}

请返回 JSON 格式如上。高频出现的组织和地点应优先提取。"""

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    # ── 容错调用 ──
    result = {}
    try:
        result = call_llm(system_prompt, user_prompt, config, timeout_override=config["llm"]["worldbuilding_timeout"], context=f"{material_id} 世界观提取")
        logger.info(f"[{material_id}] 世界观提取完成: finish={get_last_call_finish_reason()}")
        time.sleep(rate_limit)
    except Exception as e:
        logger.error(f"[{material_id}] 世界观提取失败: {e}")
        logger.warning(f"[{material_id}] 使用空结构继续，不中断流程")
        result = {
            "power_system": {},
            "geography": {},
            "factions": [],
            "lore": {}
        }

    # 写入 _index.yaml
    wb_index = {
        "power_system_levels": len(result.get("power_system", {}).get("levels", [])),
        "region_count": len(result.get("geography", {}).get("regions", [])),
        "faction_count": len(result.get("factions", [])),
        "lore_items": len(result.get("lore", {}).get("history", [])),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "llm_success": bool(result.get("power_system") or result.get("factions"))
    }

    with open(wb_dir / "_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(wb_index, f, allow_unicode=True, default_flow_style=False)

    # 写入力量体系
    if result.get("power_system"):
        with open(wb_dir / "power_system.yaml", "w", encoding="utf-8") as f:
            yaml.dump(result["power_system"], f, allow_unicode=True, default_flow_style=False)

    # 写入地理空间
    if result.get("geography"):
        with open(wb_dir / "geography.yaml", "w", encoding="utf-8") as f:
            yaml.dump(result["geography"], f, allow_unicode=True, default_flow_style=False)

    # 写入势力
    if result.get("factions"):
        with open(wb_dir / "factions.yaml", "w", encoding="utf-8") as f:
            yaml.dump(result["factions"], f, allow_unicode=True, default_flow_style=False)

    # 写入背景知识
    if result.get("lore"):
        with open(wb_dir / "lore.yaml", "w", encoding="utf-8") as f:
            yaml.dump(result["lore"], f, allow_unicode=True, default_flow_style=False)

    logger.info(
        f"[{material_id}] 世界观提取完成:\n"
        f"  力量体系: {wb_index['power_system_levels']} 个等级\n"
        f"  地理区域: {wb_index['region_count']} 个\n"
        f"  势力: {wb_index['faction_count']} 个\n"
        f"  历史事件: {wb_index['lore_items']} 个"
    )

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python worldbuilding.py <material_id>")
        sys.exit(1)

    generate_worldbuilding(sys.argv[1])