#!/usr/bin/env python
"""大纲生成：LLM 基于章级摘要池生成故事大纲结构（幕/序列/节拍/钩子网络）。

注意：此脚本必须在 chapter_analyze 完成后运行，需要 chapters.yaml 作为全局视角输入。
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

# 摘要池送给 LLM 的最大 Token 数（覆盖全书摘要）
_MAX_SUMMARY_TOKENS = 6000


def _build_summary_pool(chapters_data: list, max_tokens: int, model: str) -> str:
    """从章级摘要构建全局视角文本，按 Token 数限制。

    格式：「第N章《标题》：摘要」逐行拼接，超出 Token 限制时截断。
    """
    lines = []
    for ch in chapters_data:
        ch_num = ch.get("chapter", "?")
        title = ch.get("title", "")
        summary = ch.get("summary", "")
        if summary:
            lines.append(f"第{ch_num}章《{title}》：{summary}")

    full_text = "\n".join(lines)
    return truncate_to_tokens(full_text, max_tokens, model=model)


# ============================================================
# 大纲生成
# ============================================================
def generate_outline(material_id):
    """生成大纲：结构 + 序列 + 节拍 + 钩子网络。

    使用章级摘要池作为全局视角（而非原文前 5000 字），
    需要 chapters.yaml 已经存在（在 chapter_analyze 之后运行）。
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

    # 读取章级摘要（全书视角）
    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists() or not yaml.safe_load(chapters_file.read_text(encoding="utf-8")):
        print("警告: chapters.yaml 不存在或为空，回退到原文前 5000 字（质量受限）")
        with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
            context_text = f.read()[:5000]
        context_label = "原文摘录（前 5000 字）"
    else:
        with open(chapters_file, "r", encoding="utf-8") as f:
            chapters_data = yaml.safe_load(f) or []
        context_text = _build_summary_pool(chapters_data, _MAX_SUMMARY_TOKENS, model)
        context_label = f"章级摘要池（共 {len(chapters_data)} 章）"
        print(f"使用章级摘要池作为分析基础（{len(chapters_data)} 章）")

    # 生成 premise（一句话核心前提）
    system_prompt = """你是专业的小说结构分析师。请根据提供的内容，生成以下 JSON：
{
  "premise": "一句话核心前提（50字以内）",
  "structure_type": "三幕式/英雄之旅/多线叙事",
  "total_acts": 3,
  "theme": ["主题1", "主题2"],
  "tone": ["基调1", "基调2"]
}"""

    user_prompt = f"""请分析以下小说，提炼核心前提和整体结构：

{context_label}：
{context_text}

返回 JSON 格式如上。"""

    result = call_llm(system_prompt, user_prompt, config)

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

    # 生成序列结构
    chapter_count = len(chapter_index)
    system_prompt_seq = """你是专业的小说结构分析师。请根据章节总数和小说类型，生成合理的幕/序列划分。
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
          "description": "序列描述（50字）",
          "beats": [
            {
              "beat_number": 1,
              "title": "节拍标题",
              "chapter": 1,
              "description": "节拍描述（30字）",
              "tension": 1
            }
          ]
        }
      ]
    }
  ]
}

注意：
1. 总幕数根据结构类型决定（三幕式=3幕，英雄之旅=4幕）
2. 每幕包含 2-5 个序列
3. 每个序列包含 3-8 个节拍
4. 节拍 tension 从 1-5
5. 所有章节必须被覆盖，不要遗漏"""

    user_prompt_seq = f"""小说信息：
- 类型：{meta.get('theme', ['未知'])}
- 基调：{meta.get('tone', ['未知'])}
- 总章节数：{chapter_count}
- 结构类型：{meta.get('structure_type', '三幕式')}

请生成完整的幕/序列/节拍划分。"""

    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    outline_result = call_llm(system_prompt_seq, user_prompt_seq, config, max_tokens_override=8000)

    time.sleep(rate_limit)

    # 解析并写入文件
    acts = outline_result.get("acts", [])

    # 写入 _index.yaml
    total_sequences = sum(len(act.get("sequences", [])) for act in acts)
    index_data = {
        "structure_type": meta.get("structure_type", "三幕式"),
        "act_count": len(acts),
        "sequence_count": total_sequences,
        "hook_count": 0,  # 待钩子网络分析
        "subplot_count": 0,  # 待支线分析
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    with open(outline_dir / "_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(index_data, f, allow_unicode=True, default_flow_style=False)

    # 写入 structure.yaml
    structure_data = {"acts": acts}
    with open(outline_dir / "structure.yaml", "w", encoding="utf-8") as f:
        yaml.dump(structure_data, f, allow_unicode=True, default_flow_style=False)

    # 写入 outline_sequences 和 outline_beats 数据（供 sync_db 使用）
    sequences_data = []
    beats_data = []

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

            for beat in seq.get("beats", []):
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

    with open(outline_dir / "sequences.yaml", "w", encoding="utf-8") as f:
        yaml.dump(sequences_data, f, allow_unicode=True, default_flow_style=False)

    with open(outline_dir / "beats.yaml", "w", encoding="utf-8") as f:
        yaml.dump(beats_data, f, allow_unicode=True, default_flow_style=False)

    # 写入空的钩子网络（待 refine 阶段补充）
    with open(outline_dir / "hooks_network.yaml", "w", encoding="utf-8") as f:
        yaml.dump({"hooks": [], "subplots": []}, f, allow_unicode=True, default_flow_style=False)

    print(f"大纲生成完成: {len(acts)}幕, {total_sequences}序列, {len(beats_data)}节拍")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python generate_outline.py <material_id>")
        sys.exit(1)

    generate_outline(sys.argv[1])
