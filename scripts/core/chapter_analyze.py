#!/usr/bin/env python
"""章级分析：LLM 为每章生成摘要、出场人物、功能标签等。"""
import os
import sys
import yaml
import json
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

# ============================================================
# 配置加载
# ============================================================
def load_config():
    config_dir = Path("config")
    with open(config_dir / "llm.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# ============================================================
# LLM 调用
# ============================================================
def call_llm(system_prompt, user_prompt, config):
    """调用 LLM API 进行章级分析。"""
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
        max_tokens=config["llm"].get("max_tokens", 500),
        response_format={"type": "json_object"}
    )

    return json.loads(response.choices[0].message.content)

# ============================================================
# 章级分析主逻辑
# ============================================================
def analyze_chapter(content, chapter_info, config):
    """分析单章内容。"""
    llm_config = config.get("chapter_analyze", {})
    system_prompt = llm_config.get("system_prompt", "")

    user_prompt = f"""请分析以下章节：

章节号：{chapter_info.get('chapter', 'N/A')}
标题：{chapter_info.get('title', 'N/A')}

内容：
{content[:3000]}  # 限制长度，避免超出 token 限制

请返回 JSON 格式：
{{
  "summary": "50-100字的章节摘要，包含关键事件、情感基调、人物互动",
  "word_count": 字数,
  "characters_appear": ["出场人物名字列表"],
  "chapter_function": ["章节功能标签，从标准标签中选取"],
  "tension_level": 1-5的整数,
  "pacing": "快/慢/喘息/加速",
  "setting": ["场景类型"],
  "key_plot_point": "如果是关键节点则填写(inciting_incident/midpoint/climax/...，否则留空)"
}}"""

    return call_llm(system_prompt, user_prompt, config)

def validate_chapter_analysis(result, chapter_info):
    """校验章级分析结果。"""
    errors = []

    summary = result.get("summary", "")
    if len(summary) < 20:
        errors.append(f"章节{chapter_info['chapter']}: 摘要过短({len(summary)}字)")

    tension = result.get("tension_level")
    if tension and not (1 <= tension <= 5):
        errors.append(f"章节{chapter_info['chapter']}: tension_level 不在 1-5 范围")

    if not result.get("characters_appear"):
        errors.append(f"章节{chapter_info['chapter']}: 未识别到出场人物")

    return errors

def load_tags_dict():
    """加载标签字典用于校验。"""
    tags_file = Path("data/tags.yaml")
    if tags_file.exists():
        with open(tags_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def chapter_analyze(material_id):
    """对指定小说进行章级分析。"""
    novel_dir = Path("data/novels") / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    # 加载配置
    config = load_config()

    # 读取章节索引
    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    # 读取原文
    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    # 按章节切分原文（复用章节索引中的行号）
    lines = full_text.split("\n")
    chapters_data = []

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    for i, ch_info in enumerate(chapter_index):
        ch_num = ch_info["chapter"]
        start_line = ch_info["start_line"]
        end_line = ch_info["end_line"]

        # 提取章节内容
        chapter_text = "\n".join(lines[start_line:end_line + 1])

        print(f"正在分析第{ch_num}章: {ch_info['title']}")

        # 调用 LLM
        result = analyze_chapter(chapter_text, ch_info, config)

        # 校验
        errors = validate_chapter_analysis(result, ch_info)
        if errors:
            for e in errors:
                print(f"  警告: {e}")

        # 添加章节号
        result["chapter"] = ch_num
        result["title"] = ch_info["title"]
        chapters_data.append(result)

        # 速率限制
        if i < len(chapter_index) - 1:
            time.sleep(rate_limit)

    # 写入 chapters.yaml
    with open(novel_dir / "chapters.yaml", "w", encoding="utf-8") as f:
        yaml.dump(chapters_data, f, allow_unicode=True, default_flow_style=False)

    # 更新 meta 状态
    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)
    meta["status"] = "analyzed"
    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    print(f"章级分析完成: {len(chapters_data)} 章")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python chapter_analyze.py <material_id>")
        sys.exit(1)

    chapter_analyze(sys.argv[1])
