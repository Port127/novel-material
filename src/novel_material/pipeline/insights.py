"""Genre-aware chapter insight generation."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from novel_material.analysis_profiles import load_profiles, merge_profiles
from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import call_llm, load_config
from novel_material.infra.progress import get_pipeline_logger
from novel_material.infra.yaml_io import load_yaml, load_yaml_list, save_yaml
from novel_material.pipeline.insights_prompt import (
    build_insight_schema_text,
    build_insight_system_prompt,
    build_repair_prompt,
)
from novel_material.pipeline.profile_resolver import resolve_profile_names
from novel_material.validation.insights import validate_insight

logger = get_pipeline_logger()


def get_insight_file(novel_dir: Path, chapter_num: int) -> Path:
    """Return the per-chapter insight file path."""
    return novel_dir / "chapter_insights" / f"{chapter_num:04d}.yaml"


def split_batches(chapters: list[dict], batch_size: int) -> list[list[dict]]:
    """Split chapters into stable batches."""
    size = max(1, batch_size)
    return [chapters[i:i + size] for i in range(0, len(chapters), size)]


def build_insight_user_prompt(chapter: dict, schema_text: str) -> str:
    """Build user prompt from existing chapter analysis."""
    return f"""请基于以下章级分析生成深度创作机制分析。

章节号：{chapter.get("chapter")}
标题：{chapter.get("title")}
摘要：{chapter.get("summary", "")}
关键事件：{chapter.get("key_event", "")}
章节功能：{chapter.get("chapter_functions", [])}
人物：{chapter.get("characters_appear", [])}
张力：{chapter.get("tension_level")}
节奏：{chapter.get("pacing")}
情绪：{chapter.get("emotional_tone", [])}
场景类型：{chapter.get("scene_type", [])}
钩子：{chapter.get("hook_type", "")}

请严格返回 JSON，格式如下：
{schema_text}
"""


def build_insight_batch_user_prompt(chapters: list[dict], schema_text: str) -> str:
    """Build a compact batch prompt from existing chapter analysis."""
    lines = []
    for chapter in chapters:
        lines.append(
            "\n".join([
                f"章节号：{chapter.get('chapter')}",
                f"标题：{chapter.get('title')}",
                f"摘要：{chapter.get('summary', '')}",
                f"关键事件：{chapter.get('key_event', '')}",
                f"章节功能：{chapter.get('chapter_functions', [])}",
                f"张力：{chapter.get('tension_level')}",
                f"钩子：{chapter.get('hook_type', '')}",
            ])
        )
    joined = "\n\n---\n\n".join(lines)
    return f"""请基于以下多章章级分析生成深度创作机制分析。

要求：
- 返回 JSON 对象，顶层 items 是 JSON 数组，每个元素对应一章。
- 每个元素必须包含 chapter、common、genre、evidence、confidence。
- 不要输出 Markdown。

章节数据：
{joined}

单章 JSON 格式示例：
{schema_text}
"""


def _cap_confidence(insight: dict, errors: list[str]) -> None:
    """Cap confidence when deterministic validation found quality problems."""
    confidence = insight.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)):
        confidence = 0.0
    confidence = max(0.0, min(float(confidence), 1.0))
    if errors:
        confidence = min(confidence, 0.4)
    if not insight.get("evidence"):
        confidence = min(confidence, 0.3)
    insight["confidence"] = confidence


def _coerce_items(result: object) -> list[dict]:
    """Return generated insight items from supported LLM result shapes."""
    if isinstance(result, dict):
        items = result.get("items", [])
    elif isinstance(result, list):
        items = result
    else:
        items = []
    return [item for item in items if isinstance(item, dict)]


def generate_chapter_insights(
    material_id: str,
    start_ch: int | None = None,
    end_ch: int | None = None,
    provider: str | None = None,
    explicit_profiles: list[str] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> bool:
    """Generate genre-aware insights for analyzed chapters."""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    meta_file = novel_dir / "meta.yaml"
    meta = load_yaml(meta_file) if meta_file.exists() else {}
    profile_names = resolve_profile_names(meta, explicit_profiles=explicit_profiles)
    profile = merge_profiles(load_profiles(profile_names))

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        logger.error(f"[{material_id}] chapters.yaml 不存在，请先运行 nm pipeline analyze")
        return False

    chapters = [
        ch for ch in load_yaml_list(chapters_file)
        if isinstance(ch, dict)
        and (start_ch is None or ch.get("chapter", 0) >= start_ch)
        and (end_ch is None or ch.get("chapter", 0) <= end_ch)
    ]
    total = len(chapters)
    if total == 0:
        logger.warning(f"[{material_id}] 没有可分析章节")
        return True

    insights_dir = novel_dir / "chapter_insights"
    insights_dir.mkdir(exist_ok=True)

    config = load_config(provider)
    system_prompt = build_insight_system_prompt(profile)
    schema_text = build_insight_schema_text(profile)

    pending = [
        chapter for chapter in chapters
        if not get_insight_file(novel_dir, int(chapter["chapter"])).exists()
    ]
    done = total - len(pending)
    if progress_callback:
        progress_callback(done, total, f"断点续传：已完成 {done} 章")

    batch_size = int(config["llm"].get("insight_batch_size", 20))
    for batch_idx, batch in enumerate(split_batches(pending, batch_size), start=1):
        try:
            result = call_llm(
                system_prompt=system_prompt,
                user_prompt=build_insight_batch_user_prompt(batch, schema_text),
                config=config,
                context=f"{material_id} insights_batch#{batch_idx}",
            )
        except Exception as exc:
            logger.warning(f"[{material_id}] insight 批次 {batch_idx} 失败，写入失败占位并继续: {exc}")
            result = {}

        by_chapter = {
            int(item.get("chapter")): item
            for item in _coerce_items(result)
            if str(item.get("chapter", "")).isdigit()
        }

        for chapter in batch:
            ch_num = int(chapter["chapter"])
            raw = by_chapter.get(ch_num, {})
            repaired = False
            insight = {
                **raw,
                "schema_version": "1.0",
                "material_id": material_id,
                "chapter": ch_num,
                "title": chapter.get("title", ""),
                "profiles": profile_names,
            }
            errors = validate_insight(insight, profile)

            if errors and raw:
                repaired = True
                try:
                    repair_result = call_llm(
                        system_prompt="你是严格的 JSON 修复器，只修复格式和缺失字段，不增加无依据内容。",
                        user_prompt=build_repair_prompt(errors, raw),
                        config=config,
                        context=f"{material_id} insight#{ch_num} repair",
                    )
                except Exception as exc:
                    logger.warning(f"[{material_id}] insight 第 {ch_num} 章修复失败，保留原始结果: {exc}")
                    repair_result = raw
                if not isinstance(repair_result, dict):
                    repair_result = {}
                insight = {
                    **repair_result,
                    "schema_version": "1.0",
                    "material_id": material_id,
                    "chapter": ch_num,
                    "title": chapter.get("title", ""),
                    "profiles": profile_names,
                }
                errors = validate_insight(insight, profile)

            if not raw:
                errors = [f"批次 {batch_idx} 未返回本章结果"]

            quality = insight.get("quality")
            if not isinstance(quality, dict):
                quality = {}
            insight["quality"] = quality
            insight["quality"]["repaired"] = repaired
            insight["quality"]["validation_errors"] = errors
            _cap_confidence(insight, errors)
            save_yaml(get_insight_file(novel_dir, ch_num), insight)

            done += 1
            if progress_callback:
                progress_callback(done, total, f"完成 insight 批次 {batch_idx}: 第 {ch_num} 章")

    return True
