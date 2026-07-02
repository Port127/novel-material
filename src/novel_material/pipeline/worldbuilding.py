"""世界观提取：LLM 基于章级摘要池提取世界观设定（力量体系/地理/势力/背景知识）。

注意：此脚本在 analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。

轻量优化：
- 从章级分析的 setting 字段聚合地点统计
- 从 characters_appear 中识别组织名（如"XX成员"、"XX学生")
- 传入聚合统计给 LLM，增强提取准确性

注意：世界观向量化已移至 embed_all.py 统一处理。
"""
import sys
import time
import re
from pathlib import Path
from collections import Counter

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml, save_yaml, load_yaml_list
from novel_material.infra.llm import load_config, call_llm, start_llm_telemetry
from novel_material.infra.common import is_special_chapter_type
from novel_material.pipeline.loader import load_chapters_data, build_analysis_context
from novel_material.pipeline.worldbuilding_fallback import build_stats_seeded_entities
from novel_material.pipeline.worldbuilding_jobs import build_worldbuilding_jobs
from novel_material.infra.progress import get_pipeline_logger, save_run_history
from novel_material.infra.llm_contracts import LLMResponseContractError, require_mapping, require_mapping_list
from novel_material.worldbuilding.dimensions import resolve_worldbuilding_dimensions
from novel_material.worldbuilding.models import (
    LayeredWorldbuilding,
    WorldbuildingEntity,
    WorldbuildingIndex,
    WorldbuildingOverview,
)
from novel_material.worldbuilding.normalizer import (
    normalize_layered_worldbuilding_response,
)
from novel_material.worldbuilding.writer import write_layered_worldbuilding
from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import (
    Diagnostic,
    ProgressCounts,
    RunStatus,
    StageResult,
)

logger = get_pipeline_logger()


def normalize_worldbuilding_response(payload: object) -> dict:
    """校验并归一化世界观 LLM 响应。"""
    result = dict(require_mapping(payload, "worldbuilding"))
    for field in ("power_system", "geography", "lore"):
        value = result.get(field)
        if value is None or value == []:
            result[field] = {}
        else:
            result[field] = require_mapping(value, f"worldbuilding.{field}")
    factions = result.get("factions")
    result["factions"] = [] if factions is None else require_mapping_list(
        factions, "worldbuilding.factions"
    )
    return result


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
        if is_special_chapter_type(ch.get("type", "normal")):
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


def generate_worldbuilding(
    material_id: str,
    provider: str | None = None,
) -> StageResult:
    """提取世界观设定。

    容错策略：LLM 失败时生成空结构，不中断流程。
    返回 StageResult 表示阶段状态与质量信号。

    参数：
        material_id: 素材 ID
        provider: 服务商名称（可选，不指定则使用默认配置）
    """
    telemetry = start_llm_telemetry()

    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return _worldbuilding_missing_result(material_id)

    config = load_config(provider)
    wb_dir = novel_dir / "worldbuilding"
    wb_dir.mkdir(exist_ok=True)

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

    # 输出小说基本信息
    logger.info(
        f"[{material_id}] 小说: {title} | {chapter_count} 章 | "
        f"{word_count} 字 | 状态: {status}"
    )

    wall_start = time.monotonic()

    # 加载章节数据并聚合统计（新增）
    chapters_data = load_chapters_data(novel_dir)
    wb_stats = _aggregate_worldbuilding_stats(chapters_data) if chapters_data else {}
    org_stats = wb_stats.get("organizations", {})
    loc_stats = wb_stats.get("locations", {})
    logger.info(
        f"[{material_id}] 聚合统计: {len(org_stats)} 个组织候选, {len(loc_stats)} 个地点候选"
    )
    dimension_routing = resolve_worldbuilding_dimensions(
        meta=meta,
        navigation_dimensions=_load_navigation_dimensions(novel_dir),
        chapter_signals=wb_stats,
    )

    # 构建分析上下文（章级摘要池 > 原文片段，传入已加载的 chapters_data）
    context_text, context_label = build_analysis_context(
        novel_dir,
        config,
        chapters_data,
        material_id=material_id,
        summary_tokens_key="worldbuilding_summary_tokens",
        fallback_chars=10000,
    )
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

    dimension_lines = "\n".join(
        f"- {item.id} / {item.name}: {item.applicability}，{item.reason}"
        for item in dimension_routing.dimensions
    )

    system_prompt = """你是专业的小说世界观分析师。请根据提供的内容提取分层世界观设定，返回 JSON 格式：
{
  "overview": {
    "world_summary": "世界如何运转，以及哪些设定真正驱动剧情",
    "driving_mechanisms": [
      {"mechanism": "机制名称", "description": "说明", "related_dimensions": ["维度ID"], "evidence": [{"chapter": 1, "summary": "证据摘要"}]}
    ],
    "confidence": 0.0,
    "limitations": ["覆盖限制"]
  },
  "dimensions": [
    {"id": "维度ID", "name": "维度名", "category": "social/power/rule/space/resource/history/concept", "applicability": "applicable/not_applicable/uncertain", "reason": "判断依据", "confidence": 0.0}
  ],
  "entities": [
    {"type": "organization/location/rule/resource/power_system/social_system/history_event/concept", "name": "实体名", "description": "描述", "properties": {}, "importance": "primary/secondary/minor", "first_appearance_chapter": 1, "key_appearances": [{"chapter": 1, "role": "作用"}], "evidence": [{"chapter": 1, "basis": "fact", "summary": "证据摘要"}], "confidence": 0.0}
  ],
  "relations": [
    {"source": "实体名", "target": "实体名", "relation_type": "located_in/belongs_to/allied_with/conflicts_with/depends_on/constrains/evolves_to/interacts_with", "description": "关系说明", "evidence": [{"chapter": 1, "basis": "fact", "summary": "证据摘要"}], "confidence": 0.0}
  ]
}

注意：
1. 所有名称和描述用中文
2. 不适用维度必须在 dimensions 中标记 not_applicable，并说明原因，不要硬编不存在的修炼等级或超自然规则
3. importance 标注重要性（高频出现的组织/地点应为 primary）
4. 只提取原文中明确提到的内容；推断必须用 evidence.basis=inference 标记
5. relations 的 source/target 必须引用 entities 中的 name"""

    user_prompt = f"""请分析以下小说的世界观设定：

类型：{meta.get('theme', ['未知'])}
基调：{meta.get('tone', ['未知'])}
题材维度路由：
{dimension_lines}
{stats_context}

{context_label}：
{context_text}

请返回 JSON 格式如上。高频出现的组织和地点应优先提取。"""

    rate_limit = config["llm"].get("rate_limit_seconds", 1)

    jobs = build_worldbuilding_jobs(
        [item.model_dump(mode="json") for item in dimension_routing.dimensions],
        context_text=context_text,
        context_label=context_label,
    )

    diagnostic = None
    dimension_status: dict[str, str] = {}
    successful_layers: list[LayeredWorldbuilding] = []
    failed_dimensions: list[str] = []
    for job_index, job in enumerate(jobs):
        dimension_prompt = (
            user_prompt
            + "\n\n"
            + f"当前只抽取维度：{job.dimension_id} / {job.dimension_name}。"
            + "不要输出其他维度的实体。"
        )
        try:
            layer = normalize_layered_worldbuilding_response(
                call_llm(
                    system_prompt,
                    dimension_prompt,
                    config,
                    max_tokens_override=config["llm"].get("worldbuilding_max_tokens"),
                    timeout_override=config["llm"]["worldbuilding_timeout"],
                    context=f"{material_id} 世界观#{job.dimension_id}",
                )
            )
            successful_layers.append(_mark_layer_dimension(layer, job.dimension_id))
            dimension_status[job.dimension_id] = "llm_verified"
            logger.info(
                f"[{material_id}] 世界观维度 {job.dimension_id} 提取完成: "
                f"finish={telemetry.last.get('finish_reason', '')}"
            )
        except Exception as e:
            error_kind = (
                "schema_invalid"
                if isinstance(e, LLMResponseContractError)
                else "调用失败"
            )
            logger.error(
                f"[{material_id}] 世界观维度 {job.dimension_id} {error_kind}: {e}"
            )
            dimension_status[job.dimension_id] = "missing"
            failed_dimensions.append(job.dimension_id)
        if job_index < len(jobs) - 1:
            time.sleep(rate_limit)

    layered = _merge_dimension_layers(
        dimension_routing,
        successful_layers,
        dimension_status=dimension_status,
    )
    layered = _apply_stats_seeded_fallback(layered, dimension_status, wb_stats)

    if failed_dimensions:
        diagnostic = Diagnostic(
            code=(
                "worldbuilding_api_failed"
                if len(failed_dimensions) == len(jobs)
                else "worldbuilding_dimension_partial_failed"
            ),
            message="世界观部分维度提取失败，已保留成功维度和统计兜底",
            severity="warning",
            retryable=True,
            next_action=f"nm pipeline worldbuilding {material_id}",
        )

    write_layered_worldbuilding(novel_dir, layered)

    logger.info(
        f"[{material_id}] 世界观提取完成:\n"
        f"  维度: {layered.index.dimension_count} 个\n"
        f"  实体: {layered.index.entity_count} 个\n"
        f"  关系: {layered.index.relation_count} 条\n"
        f"  证据: {layered.index.evidence_count} 条"
    )

    # 保存运行历史
    elapsed = time.monotonic() - wall_start
    stage_result = _worldbuilding_stage_result(
        material_id,
        layered,
        elapsed=elapsed,
        diagnostic=diagnostic,
    )
    call_details = telemetry.details
    tokens_in = sum(d.get("input_tokens", 0) for d in call_details)
    tokens_out = sum(d.get("output_tokens", 0) for d in call_details)
    api_calls = len(call_details)
    save_run_history(
        novel_dir=novel_dir,
        pipeline_name="世界观提取",
        stage_times=[
            {
                "name": "世界观提取",
                "elapsed_sec": elapsed,
                "api_calls": api_calls,
                "api_errors": 0 if layered.index.llm_success else 1,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }
        ],
        total_elapsed=elapsed,
        status=stage_result.status.value,
    )

    # 世界观向量已移至 embed_all.py 统一处理
    return stage_result


def _worldbuilding_missing_result(material_id: str) -> StageResult:
    context = current_context()
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="worldbuilding",
        status=RunStatus.FAILED,
        counts=ProgressCounts(expected=1, processed=1, failed=1, remaining=0),
        diagnostics=(
            Diagnostic(
                code="worldbuilding_material_missing",
                message=f"小说目录不存在: {material_id}",
                severity="error",
                retryable=False,
            ),
        ),
        outputs={"material_id": material_id},
    )


def _worldbuilding_stage_result(
    material_id: str,
    layered: LayeredWorldbuilding,
    *,
    elapsed: float,
    diagnostic: Diagnostic | None,
) -> StageResult:
    llm_success = bool(layered.index.llm_success)
    entity_count = int(layered.index.entity_count)
    relation_count = int(layered.index.relation_count)
    evidence_count = int(layered.index.evidence_count)
    status = (
        RunStatus.SUCCESS
        if llm_success and (entity_count > 0 or evidence_count > 0)
        else RunStatus.DEGRADED
    )
    context = current_context()
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="worldbuilding",
        status=status,
        counts=ProgressCounts(
            expected=1,
            processed=1,
            succeeded=1 if status is RunStatus.SUCCESS else 0,
            degraded=1 if status is RunStatus.DEGRADED else 0,
            remaining=0,
        ),
        duration_ms=elapsed * 1000,
        diagnostics=(diagnostic,) if diagnostic else (),
        outputs={
            "material_id": material_id,
            "llm_success": llm_success,
            "entity_count": entity_count,
            "relation_count": relation_count,
            "evidence_count": evidence_count,
            "dimension_status": dict(layered.index.dimension_status),
            "source_quality_counts": dict(layered.index.source_quality_counts),
        },
    )


def _load_navigation_dimensions(novel_dir: Path) -> list[str]:
    evaluation = load_yaml(novel_dir / "evaluation.yaml")
    dimensions = evaluation.get("worldbuilding_dimensions", [])
    if isinstance(dimensions, list):
        return [str(item) for item in dimensions if str(item)]
    return []


def _apply_dimension_routing(layered, dimension_routing):
    dimensions = layered.dimensions or dimension_routing.dimensions
    source_quality_counts = _source_quality_counts(layered.entities)
    index = layered.index.model_copy(
        update={
            "dimension_count": len(dimensions),
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source_quality_counts": source_quality_counts,
        }
    )
    return layered.model_copy(
        update={
            "index": index,
            "dimensions": dimensions,
            "dimension_source": dimension_routing.source,
        }
    )


def _mark_layer_dimension(
    layered: LayeredWorldbuilding,
    dimension_id: str,
) -> LayeredWorldbuilding:
    return layered.model_copy(
        update={
            "entities": tuple(
                entity.model_copy(
                    update={
                        "dimension_id": entity.dimension_id or dimension_id,
                        "source_quality": entity.source_quality or "llm_verified",
                    }
                )
                for entity in layered.entities
            )
        }
    )


def _merge_dimension_layers(
    dimension_routing,
    layers: list[LayeredWorldbuilding],
    *,
    dimension_status: dict[str, str],
) -> LayeredWorldbuilding:
    dimensions = dimension_routing.dimensions
    entities = _dedupe_entities(
        entity for layer in layers for entity in layer.entities
    )
    entity_ids = {entity.id for entity in entities}
    relations = tuple(
        relation
        for layer in layers
        for relation in layer.relations
        if relation.source_id in entity_ids and relation.target_id in entity_ids
    )
    overview = _merge_overview(layers)
    evidence_count = sum(len(entity.evidence) for entity in entities) + sum(
        len(relation.evidence) for relation in relations
    )
    source_quality_counts = _source_quality_counts(entities)
    index = WorldbuildingIndex(
        layout="layered",
        dimension_count=len(dimensions),
        entity_count=len(entities),
        relation_count=len(relations),
        evidence_count=evidence_count,
        legacy_compatible=True,
        llm_success=bool(entities or overview.world_summary),
        created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        dimension_status=dict(dimension_status),
        source_quality_counts=source_quality_counts,
    )
    return LayeredWorldbuilding(
        index=index,
        overview=overview,
        dimensions=dimensions,
        entities=entities,
        relations=relations,
        dimension_source=dimension_routing.source,
    )


def _merge_overview(layers: list[LayeredWorldbuilding]) -> WorldbuildingOverview:
    summaries = [
        layer.overview.world_summary
        for layer in layers
        if layer.overview.world_summary
    ]
    mechanisms = [
        mechanism
        for layer in layers
        for mechanism in layer.overview.driving_mechanisms
    ]
    limitations = [
        limitation
        for layer in layers
        for limitation in layer.overview.limitations
    ]
    return WorldbuildingOverview(
        world_summary="；".join(dict.fromkeys(summaries)),
        driving_mechanisms=tuple(mechanisms),
        limitations=tuple(dict.fromkeys(limitations)),
        confidence=max((layer.overview.confidence for layer in layers), default=0.0),
    )


def _dedupe_entities(entities) -> tuple[WorldbuildingEntity, ...]:
    by_key: dict[tuple[str, str], WorldbuildingEntity] = {}
    for entity in entities:
        key = (entity.type, entity.name)
        by_key.setdefault(key, entity)
    return tuple(by_key.values())


def _apply_stats_seeded_fallback(
    layered: LayeredWorldbuilding,
    dimension_status: dict[str, str],
    wb_stats: dict,
) -> LayeredWorldbuilding:
    current_keys = {(entity.type, entity.name) for entity in layered.entities}
    seeded_payloads = [
        payload
        for payload in build_stats_seeded_entities(wb_stats)
        if (payload["type"], payload["name"]) not in current_keys
    ]
    if not seeded_payloads:
        return layered

    seeded_entities = tuple(WorldbuildingEntity(**payload) for payload in seeded_payloads)
    entities = _dedupe_entities((*layered.entities, *seeded_entities))
    status = dict(dimension_status)
    if any(entity.type == "organization" for entity in seeded_entities):
        for dimension_id in ("organization_network", "organizations"):
            if dimension_id in status:
                status[dimension_id] = "stats_seeded"
    if any(entity.type == "location" for entity in seeded_entities):
        if "locations" in status:
            status["locations"] = "stats_seeded"

    evidence_count = sum(len(entity.evidence) for entity in entities) + sum(
        len(relation.evidence) for relation in layered.relations
    )
    index = layered.index.model_copy(
        update={
            "entity_count": len(entities),
            "evidence_count": evidence_count,
            "llm_success": bool(
                any(entity.source_quality != "stats_seeded" for entity in entities)
            ),
            "dimension_status": status,
            "source_quality_counts": _source_quality_counts(entities),
        }
    )
    return layered.model_copy(update={"index": index, "entities": entities})


def _source_quality_counts(
    entities: tuple[WorldbuildingEntity, ...],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity in entities:
        quality = entity.source_quality or "llm_verified"
        counts[quality] = counts.get(quality, 0) + 1
    return counts


def _empty_layered_worldbuilding(dimension_routing) -> LayeredWorldbuilding:
    dimensions = dimension_routing.dimensions
    dimension_status = {
        dimension.id: "missing"
        for dimension in dimensions
        if dimension.applicability == "applicable"
    }
    return LayeredWorldbuilding(
        index=WorldbuildingIndex(
            layout="layered",
            dimension_count=len(dimensions),
            entity_count=0,
            relation_count=0,
            evidence_count=0,
            legacy_compatible=True,
            llm_success=False,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            dimension_status=dimension_status,
            source_quality_counts={},
        ),
        overview=WorldbuildingOverview(
            world_summary="",
            driving_mechanisms=(),
            limitations=("LLM 世界观提取失败，已保留题材维度路由结果",),
        ),
        dimensions=dimensions,
        entities=(),
        relations=(),
        dimension_source=dimension_routing.source,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python worldbuilding.py <material_id>")
        sys.exit(1)

    generate_worldbuilding(sys.argv[1])
