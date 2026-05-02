#!/usr/bin/env python
"""大纲生成：LLM 基于章级摘要池生成故事大纲结构（幕/序列/节拍/钩子网络）。

注意：此脚本必须在 chapter_analyze 完成后运行，需要 chapters.yaml 作为全局视角输入。

规模适配：
- 摘要池采用分层均匀采样（> 200 章时），确保全书首尾及中间均有代表
- beats 生成拆分为 per-sequence 循环：每个序列独立调用 LLM，避免一次性输出 1000+ 条被截断
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
from scripts.core.llm_client import load_config, call_llm
from scripts.core.chapters_loader import load_chapters_data, build_summary_pool

# 全局摘要池送给 LLM 的最大 Token 数
_MAX_SUMMARY_TOKENS = 6000
# 每个序列 beats 生成时的摘要上下文 Token 上限
_MAX_SEQ_SUMMARY_TOKENS = 2000


# ============================================================
# 第一阶段：生成幕 + 序列（不含 beats）
# ============================================================

def _generate_acts_sequences(chapter_count: int, meta: dict, context_text: str, config: dict) -> list:
    """生成完整的幕/序列划分（章节范围，不含 beats）。

    仅生成幕和序列的章节范围与描述，beats 在第二阶段逐序列生成，
    避免一次输出 1000+ 条 beats JSON 导致必然截断的问题。
    """
    system_prompt = """你是专业的小说结构分析师。请根据章节总数和小说类型，生成合理的幕/序列划分。
返回 JSON 格式：
{
  "acts": [
    {
      "act_number": 1,
      "name": "第一幕：建立",
      "chapter_start": 1,
      "chapter_end": 50,
      "sequences": [
        {
          "sequence_number": 1,
          "title": "序列标题",
          "chapter_start": 1,
          "chapter_end": 15,
          "description": "序列描述（50字内）"
        }
      ]
    }
  ]
}

注意：
1. 总幕数根据结构类型决定（三幕式=3幕，英雄之旅=4幕）
2. 每幕包含 2-5 个序列
3. 所有章节必须被覆盖，不要遗漏
4. 不需要包含 beats（节拍将在后续步骤单独生成）"""

    user_prompt = f"""小说信息：
- 类型：{meta.get('theme', ['未知'])}
- 基调：{meta.get('tone', ['未知'])}
- 总章节数：{chapter_count}
- 结构类型：{meta.get('structure_type', '三幕式')}

全书摘要参考：
{context_text}

请生成完整的幕/序列划分（仅需章节范围和描述，不需要 beats）。"""

    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=4000)
    return result.get("acts", [])


# ============================================================
# 第二阶段：逐序列生成 beats
# ============================================================

def _generate_beats_for_sequence(
    act_number: int,
    seq: dict,
    chapters_data: list,
    model: str,
    config: dict,
) -> list:
    """为单个序列生成 beats（节拍）。

    每次只处理一个序列（通常 30-150 章），上下文聚焦，输出量可控（5-15 条 beats），
    彻底避免"要求 LLM 一次输出 1600 条 beats"的结构性截断问题。
    """
    seq_start = seq.get("chapter_start", 0)
    seq_end = seq.get("chapter_end", 0)

    # 筛选本序列范围内的章节摘要
    seq_chapters = [
        ch for ch in chapters_data
        if isinstance(ch.get("chapter"), int) and seq_start <= ch["chapter"] <= seq_end
    ]

    seq_context = build_summary_pool(seq_chapters, _MAX_SEQ_SUMMARY_TOKENS, model) if seq_chapters else ""

    system_prompt = """你是专业的小说结构分析师。请为指定序列生成节拍（beats）列表。
返回 JSON 格式：
{
  "beats": [
    {
      "beat_number": 1,
      "title": "节拍标题",
      "chapter": 1,
      "description": "节拍描述（30字内）",
      "tension": 1
    }
  ]
}

注意：
1. 每个序列生成 3-10 个节拍（根据序列长度决定）
2. 节拍 tension 从 1-5
3. chapter 填写该节拍对应的最关键章节号
4. 节拍应覆盖序列的开头、中间和结尾"""

    chapter_range = f"第 {seq_start}-{seq_end} 章（共 {seq_end - seq_start + 1} 章）"
    user_prompt = f"""序列信息：
- 第 {act_number} 幕 / 序列 {seq.get('sequence_number', '?')}
- 标题：{seq.get('title', '')}
- 章节范围：{chapter_range}
- 序列描述：{seq.get('description', '')}

本序列章节摘要：
{seq_context if seq_context else '（摘要暂缺，请根据序列描述推断）'}

请为此序列生成节拍列表。"""

    result = call_llm(system_prompt, user_prompt, config, max_tokens_override=2000)
    return result.get("beats", [])


# ============================================================
# 主函数
# ============================================================

def generate_outline(material_id):
    """生成大纲：结构 + 序列 + 节拍 + 钩子网络。

    两阶段策略：
    1. 全局一次：基于分层摘要池生成前提/主题/基调 + 幕/序列划分
    2. per-sequence 循环：为每个序列独立生成 beats，上下文聚焦，输出量可控
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    config = load_config()
    model = config["llm"]["model"]
    outline_dir = novel_dir / "outline"
    outline_dir.mkdir(exist_ok=True)

    # 读取章节索引
    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)
    chapter_count = len(chapter_index)

    # 加载章节数据（优先从 chapters/ 目录，兜底 chapters.yaml）
    chapters_data = load_chapters_data(novel_dir)

    if chapters_data:
        context_text = build_summary_pool(chapters_data, _MAX_SUMMARY_TOKENS, model)
        context_label = f"章级摘要池（共 {len(chapters_data)} 章）"
        print(f"使用 {context_label} 作为分析基础")
    else:
        print("警告: 章节数据不存在或为空，回退到原文前 5000 字（质量受限）")
        with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
            context_text = f.read()[:5000]
        context_label = "原文摘录（前 5000 字）"

    # ── 第一轮：提炼前提 + 主题 + 基调 ──
    system_prompt_premise = """你是专业的小说结构分析师。请根据提供的内容，生成以下 JSON：
{
  "premise": "一句话核心前提（50字以内）",
  "structure_type": "三幕式/英雄之旅/多线叙事",
  "total_acts": 3,
  "theme": ["主题1", "主题2"],
  "tone": ["基调1", "基调2"]
}"""

    user_prompt_premise = f"""请分析以下小说，提炼核心前提和整体结构：

{context_label}：
{context_text}

返回 JSON 格式如上。"""

    result = call_llm(system_prompt_premise, user_prompt_premise, config)

    # 将 premise 写入 meta
    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    meta["premise"] = result.get("premise", "")
    meta["theme"] = result.get("theme", [])
    meta["tone"] = result.get("tone", [])
    meta["structure_type"] = result.get("structure_type", "三幕式")

    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    print(f"已生成前提: {meta['premise']}")

    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    time.sleep(rate_limit)

    # ── 第二轮：生成幕 + 序列（不含 beats）──
    print(f"生成幕/序列结构（共 {chapter_count} 章）...")
    acts = _generate_acts_sequences(chapter_count, meta, context_text, config)
    time.sleep(rate_limit)

    # ── 第三轮：逐序列生成 beats ──
    total_sequences = sum(len(act.get("sequences", [])) for act in acts)
    print(f"逐序列生成 beats（共 {total_sequences} 个序列）...")

    beats_data = []
    seq_global = 0
    for act in acts:
        for seq in act.get("sequences", []):
            seq_global += 1
            print(f"  [{seq_global}/{total_sequences}] {act.get('name', '')} / {seq.get('title', '')}")
            beats = _generate_beats_for_sequence(
                act_number=act["act_number"],
                seq=seq,
                chapters_data=chapters_data,
                model=model,
                config=config,
            )
            seq["beats"] = beats
            for beat in beats:
                beats_data.append({
                    "material_id": material_id,
                    "act": act["act_number"],
                    "sequence": seq["sequence_number"],
                    "beat": beat["beat_number"],
                    "title": beat.get("title", ""),
                    "chapter": beat.get("chapter", 0),
                    "description": beat.get("description", ""),
                    "tension": beat.get("tension", 1)
                })
            if seq_global < total_sequences:
                time.sleep(rate_limit)

    # ── 写入输出文件 ──

    # _index.yaml
    index_data = {
        "structure_type": meta.get("structure_type", "三幕式"),
        "act_count": len(acts),
        "sequence_count": total_sequences,
        "hook_count": 0,
        "subplot_count": 0,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    with open(outline_dir / "_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(index_data, f, allow_unicode=True, default_flow_style=False)

    # structure.yaml（含 beats）
    with open(outline_dir / "structure.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"acts": acts}, f, allow_unicode=True, default_flow_style=False)

    # sequences.yaml（供 sync_db 使用）
    sequences_data = []
    for act in acts:
        for seq in act.get("sequences", []):
            sequences_data.append({
                "material_id": material_id,
                "act": act["act_number"],
                "sequence": seq["sequence_number"],
                "title": seq.get("title", ""),
                "chapters_start": seq.get("chapter_start", 0),
                "chapters_end": seq.get("chapter_end", 0),
                "description": seq.get("description", "")
            })

    with open(outline_dir / "sequences.yaml", "w", encoding="utf-8") as f:
        yaml.dump(sequences_data, f, allow_unicode=True, default_flow_style=False)

    with open(outline_dir / "beats.yaml", "w", encoding="utf-8") as f:
        yaml.dump(beats_data, f, allow_unicode=True, default_flow_style=False)

    # 空钩子网络（待 refine 阶段补充）
    with open(outline_dir / "hooks_network.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"hooks": [], "subplots": []}, f, allow_unicode=True, default_flow_style=False)

    print(f"\n大纲生成完成: {len(acts)}幕, {total_sequences}序列, {len(beats_data)}节拍")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_outline.py <material_id>")
        sys.exit(1)

    generate_outline(sys.argv[1])
