"""标签生成：LLM 为整部小说生成宏观标签（类型/基调/叙事结构/风格/长板/套路识别）。

改动：
- 使用数据库动态加载标签（load_tags_for_genre）
- 分级处理新标签候选
- 支持多主题材（genre_primary 改为数组）
"""
import os
import sys
import yaml
import time
import psycopg2
from pathlib import Path

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm, get_last_call_finish_reason, get_call_details, clear_call_details
from novel_material.tags.load import load_tags_for_genre, format_tags_for_prompt, get_all_genres
from novel_material.tags.validate import validate_tag, validate_tags_batch
from novel_material.tags.scheduled import auto_approve_by_frequency
from novel_material.infra.progress import get_pipeline_logger, save_run_history

logger = get_pipeline_logger()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


def generate_tags(material_id, provider: str | None = None) -> bool:
    """为整部小说生成多维标签。

    容错策略：LLM 失败时生成默认标签，不中断流程。
    返回 True 表示成功。

    参数：
        material_id: 素材 ID
        provider: 服务商名称（可选，不指定则使用默认配置）
    """
    # 清理历史调用记录（避免累积前序流水线的 tokens）
    clear_call_details()

    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    config = load_config(provider)

    # 读取 meta 获取题材
    meta_file = novel_dir / "meta.yaml"
    if not meta_file.exists():
        logger.error(f"[{material_id}] meta.yaml 不存在: {meta_file}")
        return False

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "?")
    genre = meta.get("genre", [])
    genre_primary = genre[0] if genre else "其他"
    genre_secondary = genre[1] if len(genre) > 1 else None

    # 读取章节索引获取章数
    chapter_index_file = novel_dir / "chapter_index.yaml"
    chapter_count = 0
    if chapter_index_file.exists():
        with open(chapter_index_file, "r", encoding="utf-8") as f:
            chapter_index = yaml.safe_load(f) or []
            chapter_count = len(chapter_index)

    # 输出小说基本信息
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")

    wall_start = time.monotonic()

    # 动态加载标签（精简 prompt）
    tags_data = load_tags_for_genre(genre_primary, genre_secondary)
    logger.info(f"[{material_id}] 动态加载标签: {genre_primary} 题材，约 {count_tags(tags_data)} 个")

    # 读取原文（取前 5000 字）
    source_file = novel_dir / "source.txt"
    if not source_file.exists():
        logger.error(f"source.txt 不存在: {source_file}")
        return False

    with open(source_file, "r", encoding="utf-8") as f:
        source_text = f.read()[:5000]

    # 读取大纲结构信息（辅助标签生成）
    outline_index_file = novel_dir / "outline" / "_index.yaml"
    structure_info = ""
    if outline_index_file.exists():
        with open(outline_index_file, "r", encoding="utf-8") as f:
            outline_index = yaml.safe_load(f) or {}
        structure_info = f"结构类型：{outline_index.get('structure_type', '未知')}"

    # 构建 prompt（使用精简后的标签）
    system_prompt = build_system_prompt(tags_data)
    user_prompt = f"""请为以下小说生成标签：

{meta.get('premise', 'N/A')}
{structure_info}

原文摘录：
{source_text}

请返回 JSON 格式如上。"""

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    # ── 容错调用 ──
    result = {}
    try:
        result = call_llm(system_prompt, user_prompt, config, context=f"{material_id} 标签生成")
        logger.info(f"[{material_id}] 标签生成完成: finish={get_last_call_finish_reason()}")
        time.sleep(rate_limit)
    except Exception as e:
        logger.error(f"[{material_id}] 标签生成失败: {e}")
        logger.warning(f"[{material_id}] 使用默认标签继续，不中断流程")
        result = {
            "genre_primary": [genre_primary],
            "genre_secondary": [],
            "elements": [],
            "setting": None,
            "style": [],
            "structure": None,
            "hooks": [],
            "tropes": [],
            "themes": [],
            "genre_description": ""
        }

    # 校验并保存标签（分级处理新标签）
    tags, new_candidates = validate_and_save_tags(material_id, result, genre_primary)

    # 如果有新标签候选，触发频率自动批
    if new_candidates:
        try:
            auto_approve_by_frequency()
        except Exception as e:
            logger.warning(f"[{material_id}] 频率自动批失败: {e}，跳过")

    logger.info(
        f"[{material_id}] 标签生成完成:\n"
        f"  题材: {tags.get('genre_primary')}\n"
        f"  元素: {len(tags.get('elements', []))} 个\n"
        f"  新标签候选: {len(new_candidates)} 个"
    )

    # 保存运行历史
    elapsed = time.monotonic() - wall_start
    call_details = get_call_details()
    tokens_in = sum(d.get("input_tokens", 0) for d in call_details)
    tokens_out = sum(d.get("output_tokens", 0) for d in call_details)
    api_calls = len(call_details)
    save_run_history(
        novel_dir=novel_dir,
        pipeline_name="标签生成",
        stage_times=[{"name": "标签生成", "elapsed_sec": elapsed, "api_calls": api_calls, "api_errors": 0 if result else 1, "tokens_in": tokens_in, "tokens_out": tokens_out}],
        total_elapsed=elapsed,
        status="success"
    )

    return True


def build_system_prompt(tags_data):
    """构建 LLM prompt（使用精简后的标签）。"""

    # 组织标签为 prompt 格式
    element_prompt = format_dimension_prompt(tags_data.get("element", {}))
    setting_prompt = format_dimension_prompt(tags_data.get("setting", {}))
    style_prompt = format_dimension_prompt(tags_data.get("style", {}))
    structure_prompt = format_dimension_prompt(tags_data.get("structure", {}))

    # 获取所有一级题材
    all_genres = get_all_genres()

    # 构建 JSON 模板（不使用 f-string 内的花括号）
    json_template = """{
  "genre_primary": ["主题材（选 1-2 个一级题材）"],
  "genre_secondary": ["次题材（选 0-2 个二级题材）"],
  "elements": ["元素标签（选 3-8 个，必须从以下列表选取)"],
  "setting": "世界观力量体系（从下列选 1 个）",
  "style": ["风格标签（选 1-3 个，必须从以下列表选取)"],
  "structure": "叙事结构（从下列选 1 个）",
  "hooks": ["长板/亮点（1-3 个，自由填写）"],
  "tropes": ["套路识别（1-3 个，自由填写）"],
  "themes": ["主题（1-3 个，自由填写）"],
  "genre_description": "题材自由描述（一句话，可选）"
}"""

    return f"""你是专业的小说标签标注师。请为小说生成以下多维标签：

可用题材: {all_genres}

元素标签可选: {element_prompt}

世界观体系可选: {setting_prompt}

风格标签可选: {style_prompt}

叙事结构可选: {structure_prompt}

返回格式示例:
{json_template}

注意：
1. genre_primary 可以选择 1-2 个一级题材（跨题材小说）
2. elements/style 必须从上面提供的字典中选取，不得编造
3. setting/structure 必须从上面提供的字典中选取
4. hooks/tropes/themes/genre_description 可以自由填写"""


def format_dimension_prompt(dim_data):
    """格式化维度标签为 prompt 字符串。"""
    lines = []
    for domain, groups in dim_data.items():
        for group, tags in groups.items():
            tags_str = ", ".join(tags[:15])  # 限制显示数量
            lines.append(f"  《{group}》: {tags_str}…")
    return "\n".join(lines) if lines else "（无限制）"


def count_tags(tags_data):
    """统计标签总数。"""
    total = 0
    for dim, domains in tags_data.items():
        for dom, groups in domains.items():
            for group, tag_list in groups.items():
                total += len(tag_list)
    return total


def validate_and_save_tags(material_id, llm_result, context_genre):
    """校验并保存标签，处理新标签候选。"""

    tags = {"material_id": material_id}
    new_candidates = []

    conn = get_connection()
    conn.autocommit = True

    # === Level 3: 题材严格校验 ===
    primary = llm_result.get("genre_primary", [])
    if isinstance(primary, str):
        primary = [primary]

    valid_genres, new_genres = validate_genres(conn, primary)
    tags["genre_primary"] = valid_genres

    # 如果所有题材都无效，使用"其他"
    if not valid_genres:
        tags["genre_primary"] = ["其他"]
        logger.warning(f"小说 {material_id} 无法归类，使用'其他'")

    # 新题材候选入库
    for g in new_genres:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO new_genre_candidates (genre, source_material, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (genre) DO UPDATE SET occurrence_count = new_genre_candidates.occurrence_count + 1
            """, [g, material_id, llm_result.get("genre_description")])
        logger.warning(f"发现新题材候选: {g}")

    # === Level 1/2: 白名单字段校验 ===
    for key in ["elements", "style"]:
        value = llm_result.get(key, [])

        if isinstance(value, list):
            valid, invalid = validate_tags_batch(key, value)
            tags[key] = valid

            # 新标签候选入库
            for tag in invalid:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO new_tag_candidates (dimension, tag, context_genre, source_material)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (dimension, tag) DO UPDATE SET occurrence_count = new_tag_candidates.occurrence_count + 1
                    """, [key, tag, context_genre, material_id])
                new_candidates.append({"dimension": key, "tag": tag})

            if invalid:
                logger.warning(f"发现新标签候选: {key}/{invalid}")

    # === Level 2: setting/structure 校验 ===
    for key in ["setting", "structure"]:
        value = llm_result.get(key)

        if value:
            canonical = validate_tag(key, value)
            if canonical:
                tags[key] = canonical
            else:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO new_tag_candidates (dimension, tag, context_genre, source_material)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (dimension, tag) DO UPDATE SET occurrence_count = new_tag_candidates.occurrence_count + 1
                    """, [key, value, context_genre, material_id])
                new_candidates.append({"dimension": key, "tag": value})
                logger.warning(f"发现新标签候选: {key}/{value}")

    # === Level 0: 自由字段自动入库 ===
    for key in ["hooks", "tropes", "themes", "genre_description"]:
        value = llm_result.get(key, [])
        if isinstance(value, str):
            value = [value] if value else []
        tags[key] = value

        # 统计自由标签
        for tag in value:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO free_tags_stats (dimension, tag)
                    VALUES (%s, %s)
                    ON CONFLICT (dimension, tag) DO UPDATE SET
                        occurrence_count = free_tags_stats.occurrence_count + 1,
                        last_seen = NOW()
                """, [key, tag])

    conn.close()

    # 保存到 tags.yaml
    novel_dir = NOVELS_DIR / material_id
    with open(novel_dir / "tags.yaml", "w", encoding="utf-8") as f:
        yaml.dump(tags, f, allow_unicode=True, default_flow_style=False)

    # 更新 meta.yaml
    with open(novel_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    meta["genre"] = tags.get("genre_primary", [])
    meta["tags"] = tags

    with open(novel_dir / "meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    return tags, new_candidates


def validate_genres(conn, genre_list):
    """校验题材是否合法。"""

    with conn.cursor() as cur:
        cur.execute("SELECT genre_primary FROM genre_domain_map")
        valid_set = set(row[0] for row in cur.fetchall())

    valid = []
    new = []

    for g in genre_list:
        if g in valid_set:
            valid.append(g)
        else:
            new.append(g)

    return valid, new


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python tags.py <material_id>")
        sys.exit(1)

    generate_tags(sys.argv[1])