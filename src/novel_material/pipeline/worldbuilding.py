"""世界观提取：LLM 基于章级摘要池提取世界观设定（力量体系/地理/势力/背景知识）。

注意：此脚本在 analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。
"""
import sys
import yaml
import time
from pathlib import Path

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, load_provider_config, call_llm, get_last_call_finish_reason
from novel_material.pipeline.loader import load_chapters_data, build_summary_pool
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()


def _build_context(novel_dir: Path, config: dict) -> tuple[str, str]:
    """构建分析上下文，优先使用章级摘要池，兜底读原文片段。

    章数 > 200 时自动启用分层均匀采样，确保全书首尾及中间均有代表。
    """
    model = config["llm"]["model"]
    chapters_data = load_chapters_data(novel_dir)
    if chapters_data:
        pool = build_summary_pool(chapters_data, config["llm"]["worldbuilding_summary_tokens"], model)
        return pool, f"章级摘要池（共 {len(chapters_data)} 章）"

    logger.warning("章节数据不存在或为空，回退到原文前 10000 字（质量受限）")
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
        logger.error(f"小说目录不存在: {novel_dir}")
        return False

    config = load_provider_config(provider) if provider else load_config()
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
    logger.info(f"小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")

    # 构建分析上下文（章级摘要池 > 原文片段）
    context_text, context_label = _build_context(novel_dir, config)
    logger.info(f"使用 {context_label} 作为分析基础")

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
3. importance 标注重要性
4. 只提取原文中明确提到的内容，不要编造"""

    user_prompt = f"""请分析以下小说的世界观设定：

类型：{meta.get('theme', ['未知'])}
基调：{meta.get('tone', ['未知'])}

{context_label}：
{context_text}

请返回 JSON 格式如上。"""

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    # ── 容错调用 ──
    result = {}
    try:
        result = call_llm(system_prompt, user_prompt, config, timeout_override=config["llm"]["worldbuilding_timeout"], context="世界观提取")
        logger.info(f"世界观提取完成: finish={get_last_call_finish_reason()}")
        time.sleep(rate_limit)
    except Exception as e:
        logger.error(f"世界观提取失败: {e}")
        logger.warning("使用空结构继续，不中断流程")
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

    logger.info(f"世界观提取完成:\n"
                f"  力量体系: {wb_index['power_system_levels']} 个等级\n"
                f"  地理区域: {wb_index['region_count']} 个\n"
                f"  势力: {wb_index['faction_count']} 个\n"
                f"  历史事件: {wb_index['lore_items']} 个")

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python worldbuilding.py <material_id>")
        sys.exit(1)

    generate_worldbuilding(sys.argv[1])