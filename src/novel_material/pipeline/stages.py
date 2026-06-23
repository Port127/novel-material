"""供 PipelineOrchestrator 调用的统一 StageResult 入口。"""

from __future__ import annotations

from novel_material.audit.service import audit_material, audit_to_stage_result

from .analyze import chapter_analyze
from .characters import generate_characters
from .evaluate import run_evaluation
from .ingest import ingest_file
from .insights import generate_chapter_insights
from .outline import generate_outline
from .refine import refine
from .stage_contracts import adapt_stage_result
from .tags import generate_tags
from .worldbuilding import generate_worldbuilding


def run_ingest_stage(*args, **kwargs):
    return adapt_stage_result(
        "ingest",
        ingest_file(*args, **kwargs),
        output_key="material_id",
    )


def run_evaluation_stage(*args, **kwargs):
    return adapt_stage_result("evaluation", run_evaluation(*args, **kwargs))


def run_analyze_stage(*args, **kwargs):
    return adapt_stage_result("analyze", chapter_analyze(*args, **kwargs))


def run_outline_stage(*args, **kwargs):
    return adapt_stage_result("outline", generate_outline(*args, **kwargs))


def run_worldbuilding_stage(*args, **kwargs):
    return adapt_stage_result("worldbuilding", generate_worldbuilding(*args, **kwargs))


def run_characters_stage(*args, **kwargs):
    return adapt_stage_result("characters", generate_characters(*args, **kwargs))


def run_tags_stage(*args, **kwargs):
    return adapt_stage_result("tags", generate_tags(*args, **kwargs))


def run_insights_stage(*args, **kwargs):
    return adapt_stage_result("insights", generate_chapter_insights(*args, **kwargs))


def run_refine_stage(*args, **kwargs):
    return adapt_stage_result("refine", refine(*args, **kwargs))


def run_artifact_audit_stage(material_id: str, **kwargs):
    audit = audit_material(material_id, **kwargs)
    return audit_to_stage_result(audit)


__all__ = [
    "run_analyze_stage",
    "run_artifact_audit_stage",
    "run_characters_stage",
    "run_evaluation_stage",
    "run_ingest_stage",
    "run_insights_stage",
    "run_outline_stage",
    "run_refine_stage",
    "run_tags_stage",
    "run_worldbuilding_stage",
]
