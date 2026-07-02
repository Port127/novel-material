"""人物提取入口：统计驱动的分层人物提取。

此模块包含 generate_characters 主函数，
调用各子模块完成人物提取任务。

分层策略：
1. 统计章节出场人物频率，筛选候选人（>=5章）
2. 分三层处理：
   - 核心层（>=50章）：完整档案（心理分析、弧线、关键事件）
   - 配角层（>=10章）：标准档案（基础信息 + 关系）
   - 次要层（>=5章）：精简档案（仅基础信息）

注意：人物向量化已移至 embed_all.py 统一处理。
"""
import sys
import time
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml, save_yaml, load_yaml_list
from novel_material.infra.llm import load_config, start_llm_telemetry
from novel_material.pipeline.loader import load_chapters_data, build_analysis_context
from novel_material.infra.progress import get_pipeline_logger, PipelineRunner

from novel_material.pipeline.characters_selection import (
    BiographySelection,
    BiographyTarget,
    build_character_signals,
    select_biography_targets,
)
from novel_material.pipeline.characters_stats import CHARACTER_THRESHOLDS, VALID_ROLES, _extract_appearance_stats
from novel_material.pipeline.characters_profile import (
    _build_basic_profile_from_stats,
    _build_profile_from_character,
    _save_character_profile,
    _load_existing_profiles,
)
from novel_material.pipeline.characters_quality import build_character_quality_counts
from novel_material.pipeline.characters_layer import _extract_character_batch
from novel_material.pipeline.evaluation_models import (
    EvaluationNavigation,
    load_evaluation_navigation,
)
from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import (
    Diagnostic,
    ProgressCounts,
    RunStatus,
    StageResult,
)

logger = get_pipeline_logger()


def generate_characters(
    material_id,
    progress_callback: Callable[[int, int, str], None] | None = None,
    provider: str | None = None,
    repair_characters: tuple[str, ...] = (),
) -> bool | StageResult:
    """统计驱动的人物提取。

    新策略：
    1. 基于出场统计筛选候选人（分层：核心/配角/次要）
    2. 分批调用LLM补充档案详情
    3. LLM失败时使用出场统计生成基础档案兜底

    容错策略：任何轮次失败时使用出场统计兜底，不中断流程。
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
    repair_names = tuple(dict.fromkeys(name for name in repair_characters if name))
    char_dir = novel_dir / "characters"
    char_dir.mkdir(exist_ok=True)
    profiles_dir = char_dir / "profiles"
    profiles_dir.mkdir(exist_ok=True)

    # 读取 meta
    meta = load_yaml(novel_dir / "meta.yaml")

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "raw")

    # 读取章节索引获取章数
    chapter_index_file = novel_dir / "chapter_index.yaml"
    chapter_count = 0
    if chapter_index_file.exists():
        chapter_index = load_yaml_list(chapter_index_file)
        chapter_count = len(chapter_index)

    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")

    runner = PipelineRunner(
        name="人物提取",
        total_stages=4,  # 核心/配角/次要/向量化
        novel_dir=novel_dir,
        material_id=material_id,
        novel_info={"name": title, "chapter_count": chapter_count, "word_count": word_count}
    )
    wall_start = time.monotonic()

    # 加载章节数据并统计出场人物
    chapters_data = load_chapters_data(novel_dir)
    appearance_stats = _extract_appearance_stats(chapters_data) if chapters_data else {}
    logger.info(f"[{material_id}] 出场人物统计: {len(appearance_stats)} 个不同人物")

    navigation = load_evaluation_navigation(novel_dir) or EvaluationNavigation()
    signals = build_character_signals(chapters_data, navigation)
    selection = select_biography_targets(signals)
    if repair_names:
        selection = _repair_selection(repair_names, selection, appearance_stats)
    target_names = {target.name for target in selection.targets}
    qualified_candidates = _qualified_character_candidates(appearance_stats)
    remaining_candidates = [] if repair_names else [
        (name, count) for name, count in qualified_candidates if name not in target_names
    ]
    supporting_candidates = [
        (name, count)
        for name, count in remaining_candidates
        if count >= CHARACTER_THRESHOLDS["supporting"]
    ]
    minor_candidates = [
        (name, count)
        for name, count in remaining_candidates
        if count < CHARACTER_THRESHOLDS["supporting"]
    ]

    logger.info(
        f"[{material_id}] 人物选择结果:\n"
        f"  完整小传目标: {len(selection.targets)} 人\n"
        f"  简档配角（>= {CHARACTER_THRESHOLDS['supporting']} 章）: {len(supporting_candidates)} 人\n"
        f"  简档次要（>= {CHARACTER_THRESHOLDS['minor']} 章）: {len(minor_candidates)} 人\n"
        f"  选择原因: {selection.selection_reason}"
    )

    # 构建分析上下文
    context_text, context_label = build_analysis_context(
        novel_dir, config, chapters_data, material_id=material_id,
        summary_tokens_key="characters_summary_tokens",
        fallback_chars=8000,
    )
    context_chars = len(context_text)
    logger.info(f"[{material_id}] 输入: {context_chars} 字符 | {context_label}")

    # 加载已保存的人物（断点续传）
    existing_profiles, existing_names = _load_existing_profiles(char_dir)
    if repair_names:
        _delete_profiles_by_name(profiles_dir, set(repair_names))
        existing_profiles, existing_names = _load_existing_profiles(char_dir)
    if existing_profiles:
        logger.info(f"[{material_id}] 断点续传：已保存 {len(existing_profiles)} 个人物")
    completed_biography_names = {
        profile.get("name")
        for profile in existing_profiles
        if profile.get("biography_complete") is True
    }
    core_candidates = [
        (target.name, target.appearance_count)
        for target in selection.targets
        if target.name not in completed_biography_names
    ]

    # 收集所有关系
    all_relationships = []

    # 收集已有人物的关系
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

    idx = len(existing_profiles)
    total_batches = 3

    new_core_count = 0
    core_telemetry = start_llm_telemetry()
    if core_candidates:
        if progress_callback:
            progress_callback(0, total_batches, f"提取核心人物 ({len(core_candidates)} 人)")

        try:
            core_characters = _extract_character_batch(
                core_candidates, "core", context_text, context_label,
                meta, config, material_id=material_id, chapters_data=chapters_data
            )
        except Exception as e:
            logger.error(f"[{material_id}] 核心人物提取失败: {e}")
            logger.warning(f"[{material_id}] 使用出场统计生成基础档案兜底")
            core_characters = []
            for name, count in core_candidates:
                profile = _build_basic_profile_from_stats(name, count, "supporting", chapters_data)
                core_characters.append(profile)

        for ch in core_characters:
            name = ch.get("name")
            if not name or name in completed_biography_names:
                continue

            role = ch.get("role", "supporting")
            if role not in VALID_ROLES:
                role = "supporting"

            profile = _build_profile_from_character(ch, role)
            profile["profile_level"] = profile.get("profile_level", "full")
            profile["biography_complete"] = profile.get("biography_complete", True)
            profile["appearance_count"] = appearance_stats.get(name, 0)
            _save_character_profile(profiles_dir, idx, profile, name)
            existing_profiles.append(profile)
            existing_names.add(name)
            idx += 1
            new_core_count += 1

            for rel in ch.get("relationships", []):
                all_relationships.append({
                    "from": name,
                    "to": rel.get("character"),
                    "relationship": rel.get("relationship"),
                    "nature": rel.get("nature", "unknown")
                })

        logger.info(f"[{material_id}] 核心人物: 保存 {new_core_count} 人")

        core_elapsed = time.monotonic() - wall_start
        call_details = core_telemetry.details
        core_tokens_in = sum(d.get("input_tokens", 0) for d in call_details)
        core_tokens_out = sum(d.get("output_tokens", 0) for d in call_details)
        runner.record_stage_complete(
            stage_name=f"核心人物({len(core_candidates)}人)",
            elapsed=core_elapsed,
            api_calls=1,
            api_errors=0 if new_core_count > 0 else 1,
            tokens_in=core_tokens_in,
            tokens_out=core_tokens_out
        )
        wall_start = time.monotonic()
    else:
        logger.info(f"[{material_id}] 无需新建完整小传目标")

    if progress_callback:
        progress_callback(1, total_batches, f"核心人物完成 ({new_core_count} 人)")

    new_supporting_count = 0
    supporting_telemetry = start_llm_telemetry()
    if supporting_candidates:
        if progress_callback:
            progress_callback(1, total_batches, f"提取配角 ({len(supporting_candidates)} 人)")

        try:
            supporting_characters = _extract_character_batch(
                supporting_candidates, "supporting", context_text, context_label,
                meta, config, material_id=material_id, chapters_data=chapters_data
            )
        except Exception as e:
            logger.error(f"[{material_id}] 配角提取失败: {e}")
            logger.warning(f"[{material_id}] 使用出场统计生成基础档案兜底")
            supporting_characters = []
            for name, count in supporting_candidates:
                profile = _build_basic_profile_from_stats(name, count, "supporting", chapters_data)
                supporting_characters.append(profile)

        for ch in supporting_characters:
            name = ch.get("name")
            if not name or name in existing_names:
                continue

            profile = _build_profile_from_character(ch, "supporting")
            if profile.get("profile_level") != "fallback":
                profile["profile_level"] = "brief"
                profile["biography_complete"] = False
            profile["appearance_count"] = appearance_stats.get(name, 0)
            _save_character_profile(profiles_dir, idx, profile, name)
            existing_profiles.append(profile)
            existing_names.add(name)
            idx += 1
            new_supporting_count += 1

            for rel in ch.get("relationships", []):
                all_relationships.append({
                    "from": name,
                    "to": rel.get("character"),
                    "relationship": rel.get("relationship"),
                    "nature": rel.get("nature", "unknown")
                })

        logger.info(f"[{material_id}] 配角: 保存 {new_supporting_count} 人")

        supporting_elapsed = time.monotonic() - wall_start
        call_details = supporting_telemetry.details
        supporting_tokens_in = sum(d.get("input_tokens", 0) for d in call_details)
        supporting_tokens_out = sum(d.get("output_tokens", 0) for d in call_details)
        runner.record_stage_complete(
            stage_name=f"配角({len(supporting_candidates)}人)",
            elapsed=supporting_elapsed,
            api_calls=1,
            api_errors=0 if new_supporting_count > 0 else 1,
            tokens_in=supporting_tokens_in,
            tokens_out=supporting_tokens_out
        )
        wall_start = time.monotonic()
    else:
        logger.info(f"[{material_id}] 无配角候选人（>= {CHARACTER_THRESHOLDS['supporting']} 章）")

    if progress_callback:
        progress_callback(2, total_batches, f"配角完成 ({new_supporting_count} 人)")

    new_minor_count = 0
    minor_telemetry = start_llm_telemetry()
    if minor_candidates:
        if progress_callback:
            progress_callback(2, total_batches, f"提取次要人物 ({len(minor_candidates)} 人)")

        try:
            minor_characters = _extract_character_batch(
                minor_candidates, "minor", context_text, context_label,
                meta, config, material_id=material_id, chapters_data=chapters_data
            )
        except Exception as e:
            logger.error(f"[{material_id}] 次要人物提取失败: {e}")
            logger.warning(f"[{material_id}] 使用出场统计生成基础档案兜底")
            minor_characters = []
            for name, count in minor_candidates:
                profile = _build_basic_profile_from_stats(name, count, "minor", chapters_data)
                minor_characters.append(profile)

        for ch in minor_characters:
            name = ch.get("name")
            if not name or name in existing_names:
                continue

            profile = _build_profile_from_character(ch, "minor")
            if profile.get("profile_level") != "fallback":
                profile["profile_level"] = "brief"
                profile["biography_complete"] = False
            profile["appearance_count"] = appearance_stats.get(name, 0)
            _save_character_profile(profiles_dir, idx, profile, name)
            existing_profiles.append(profile)
            existing_names.add(name)
            idx += 1
            new_minor_count += 1

            for rel in ch.get("relationships", []):
                all_relationships.append({
                    "from": name,
                    "to": rel.get("character"),
                    "relationship": rel.get("relationship"),
                    "nature": rel.get("nature", "unknown")
                })

        logger.info(f"[{material_id}] 次要人物: 保存 {new_minor_count} 人")

        minor_elapsed = time.monotonic() - wall_start
        call_details = minor_telemetry.details
        minor_tokens_in = sum(d.get("input_tokens", 0) for d in call_details)
        minor_tokens_out = sum(d.get("output_tokens", 0) for d in call_details)
        runner.record_stage_complete(
            stage_name=f"次要人物({len(minor_candidates)}人)",
            elapsed=minor_elapsed,
            api_calls=1,
            api_errors=0 if new_minor_count > 0 else 1,
            tokens_in=minor_tokens_in,
            tokens_out=minor_tokens_out
        )
    else:
        logger.info(f"[{material_id}] 无次要人物候选人（>= {CHARACTER_THRESHOLDS['minor']} 章）")

    if progress_callback:
        progress_callback(3, total_batches, f"完成: {new_core_count + new_supporting_count + new_minor_count} 人")

    # 合并所有人物
    all_characters = existing_profiles
    quality_counts = build_character_quality_counts(all_characters)
    repair_counts = {
        "attempted": sum(
            1 for c in all_characters if int(c.get("repair_attempts") or 0) > 0
        ),
        "succeeded": sum(
            1
            for c in all_characters
            if int(c.get("repair_attempts") or 0) > 0
            and c.get("source_quality") == "llm_repaired"
        ),
        "failed": sum(
            1
            for c in all_characters
            if int(c.get("repair_attempts") or 0) > 0
            and c.get("source_quality") != "llm_repaired"
        ),
    }

    # 关系去重
    seen_pairs = set()
    unique_relationships = []
    for rel in all_relationships:
        if not rel.get("from") or not rel.get("to"):
            continue
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
        "biography_target_count": len(selection.targets),
        "biography_completed_count": sum(
            1
            for c in all_characters
            if c.get("name") in target_names and c.get("biography_complete") is True
        ),
        "biography_failed_count": max(
            0,
            len(selection.targets)
            - sum(
                1
                for c in all_characters
                if c.get("name") in target_names
                and c.get("biography_complete") is True
            ),
        ),
        "biography_selection_reason": selection.selection_reason,
        "repair_requested": bool(repair_names),
        "quality_counts": quality_counts,
        "repair_counts": repair_counts,
        "biography_targets": [
            {
                "name": target.name,
                "score": target.score,
                "reasons": list(target.reasons),
            }
            for target in selection.targets
        ],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }

    save_yaml(char_dir / "_index.yaml", char_index)

    # 写入关系网
    save_yaml(char_dir / "relationships.yaml", {"relationships": unique_relationships})

    logger.info(
        f"[{material_id}] 人物提取完成:\n"
        f"  总人物: {char_index['character_count']}\n"
        f"  主角: {char_index['protagonist_count']}\n"
        f"  反派: {char_index['antagonist_count']}\n"
        f"  配角: {char_index['supporting_count']}\n"
        f"  次要: {char_index['minor_count']}\n"
        f"  关系: {len(unique_relationships)} 条"
    )

    fallback_count = sum(
        1 for item in all_characters if item.get("profile_level") == "fallback"
    )
    stage_status, diagnostic = _characters_stage_status(
        biography_target_count=char_index["biography_target_count"],
        biography_completed_count=char_index["biography_completed_count"],
        biography_failed_count=char_index["biography_failed_count"],
        fallback_count=fallback_count,
    )
    runner.save_history(status=stage_status.value)

    # 人物向量已移至 embed_all.py 统一处理
    context = current_context()
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="characters",
        status=stage_status,
        counts=ProgressCounts(
            expected=char_index["biography_target_count"],
            processed=char_index["biography_target_count"],
            succeeded=char_index["biography_completed_count"],
            degraded=char_index["biography_failed_count"],
            failed=0,
            remaining=0,
        ),
        diagnostics=(diagnostic,) if diagnostic else (),
        outputs={
            "character_count": len(all_characters),
            "fallback_count": fallback_count,
            **char_index,
        },
    )


def _characters_stage_status(
    *,
    biography_target_count: int,
    biography_completed_count: int,
    biography_failed_count: int,
    fallback_count: int,
) -> tuple[RunStatus, Diagnostic | None]:
    if biography_target_count > 0 and biography_completed_count == 0:
        return RunStatus.DEGRADED, Diagnostic(
            code="character_biography_all_failed",
            message="核心人物完整小传目标全部失败，已保留简档或 fallback 档案",
            severity="warning",
            retryable=True,
            next_action="nm pipeline characters <material_id>",
        )
    if biography_failed_count > 0 or fallback_count > 0:
        return RunStatus.DEGRADED, Diagnostic(
            code="character_biography_partial_failed",
            message="部分人物完整小传失败，已保留可用档案",
            severity="warning",
            retryable=True,
        )
    return RunStatus.SUCCESS, None


def _qualified_character_candidates(appearance_stats: dict[str, int]) -> list[tuple[str, int]]:
    """返回达到人物候选最低门槛的名单。"""
    minor_threshold = CHARACTER_THRESHOLDS["minor"]
    candidates = [
        (name, count)
        for name, count in appearance_stats.items()
        if count >= minor_threshold
    ]
    candidates.sort(key=lambda item: (-item[1], item[0]))
    return candidates


def _repair_selection(
    repair_names: tuple[str, ...],
    base_selection: BiographySelection,
    appearance_stats: dict[str, int],
) -> BiographySelection:
    """把修复名单转换为只包含指定人物的完整小传选择。"""
    base_targets = {target.name: target for target in base_selection.targets}
    targets = []
    for name in repair_names:
        base = base_targets.get(name)
        targets.append(
            BiographyTarget(
                name=name,
                score=base.score if base else 0.0,
                reasons=(
                    *((base.reasons if base else ())),
                    "repair_requested",
                ),
                appearance_count=appearance_stats.get(name, 0),
                role_hint=base.role_hint if base else "supporting",
            )
        )
    return BiographySelection(
        targets=tuple(targets),
        selection_reason="repair_requested",
        qualified_count=len(targets),
    )


def _delete_profiles_by_name(profiles_dir: Path, names: set[str]) -> None:
    """删除指定人物现有 profile 文件，其他人物文件保持不变。"""
    for profile_path in profiles_dir.glob("*.yaml"):
        profile = load_yaml(profile_path)
        if profile.get("name") in names:
            profile_path.unlink()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python characters_core.py <material_id>")
        sys.exit(1)

    generate_characters(sys.argv[1])
