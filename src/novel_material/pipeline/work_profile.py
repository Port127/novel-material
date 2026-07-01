"""作品画像生成阶段：从稳定产物生成 work_profile.yaml。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import call_llm, load_config
from novel_material.infra.yaml_io import load_yaml, load_yaml_list, save_yaml
from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import (
    Diagnostic,
    ProgressCounts,
    RunStatus,
    StageResult,
)
from novel_material.worldbuilding.reader import load_worldbuilding_view

from .work_profile_models import normalize_work_profile_response
from .work_profile_prompt import build_work_profile_prompt


def generate_work_profile(
    material_id: str,
    provider: str | None = None,
) -> StageResult:
    """从稳定产物生成 work_profile.yaml，不读取完整原文。"""
    novel_dir = NOVELS_DIR / material_id
    context = _build_profile_context(novel_dir, material_id)
    if context is None:
        return _profile_result(
            RunStatus.FAILED,
            diagnostic=Diagnostic(
                code="work_profile_evidence_missing",
                message="生成作品画像所需 meta.yaml 或 chapters.yaml 不完整",
                severity="error",
                retryable=True,
            ),
        )

    config = load_config(provider)
    system_prompt, user_prompt = build_work_profile_prompt(context)
    timeout = config.get("llm", {}).get("profile_timeout")
    try:
        response = call_llm(
            system_prompt,
            user_prompt,
            config,
            timeout_override=timeout,
            context=f"{material_id} 作品画像",
        )
    except Exception as exc:
        return _profile_result(
            RunStatus.FAILED,
            diagnostic=Diagnostic(
                code="work_profile_api_failed",
                message=f"作品画像生成失败: {type(exc).__name__}",
                severity="error",
                retryable=True,
            ),
        )

    try:
        profile = normalize_work_profile_response(
            response,
            material_id=material_id,
            title=str(context.get("title") or ""),
        )
    except ValueError as exc:
        return _profile_result(
            RunStatus.FAILED,
            diagnostic=Diagnostic(
                code="work_profile_schema_invalid",
                message=f"作品画像生成失败: {type(exc).__name__}",
                severity="error",
                retryable=True,
            ),
        )

    save_yaml(novel_dir / "work_profile.yaml", profile.model_dump(mode="json"))
    return _profile_result(RunStatus.SUCCESS, written=True)


def _profile_result(
    status: RunStatus,
    *,
    diagnostic: Diagnostic | None = None,
    written: bool = False,
) -> StageResult:
    context = current_context()
    return StageResult(
        stage_id=context.stage_id if context and context.stage_id else new_id("stage"),
        name="profile",
        status=status,
        counts=ProgressCounts(
            expected=1,
            processed=1,
            succeeded=1 if status is RunStatus.SUCCESS else 0,
            failed=1 if status is RunStatus.FAILED else 0,
            remaining=0,
        ),
        diagnostics=(diagnostic,) if diagnostic else (),
        outputs={"work_profile_written": written},
    )


def _build_profile_context(novel_dir: Path, material_id: str) -> dict[str, Any] | None:
    meta_path = novel_dir / "meta.yaml"
    chapters_path = novel_dir / "chapters.yaml"
    if not meta_path.is_file() or not chapters_path.is_file():
        return None

    meta = load_yaml(meta_path)
    chapters = _compact_chapters(load_yaml_list(chapters_path))
    if not chapters:
        return None

    return {
        "material_id": material_id,
        "title": meta.get("name") or meta.get("title") or "",
        "genre": meta.get("genre", []),
        "facts": {
            "chapters": chapters,
            "outline": _compact_outline(novel_dir),
            "characters": _compact_characters(novel_dir),
            "worldbuilding_entities": _compact_worldbuilding(novel_dir),
            "tags": load_yaml(novel_dir / "tags.yaml"),
        },
        "limits": {
            "role": "work_profile.yaml 仅作为写作 Agent 的作品级入口，不作为事实来源",
            "evidence_required": True,
        },
    }


def _compact_chapters(chapters: list[dict]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in chapters[:80]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "chapter": item.get("chapter"),
                "summary": item.get("summary", ""),
                "key_event": item.get("key_event", ""),
                "characters_appear": item.get("characters_appear", []),
                "setting": item.get("setting", []),
            }
        )
    return compact


def _compact_outline(novel_dir: Path) -> dict[str, Any]:
    index = load_yaml(novel_dir / "outline" / "_index.yaml")
    if not index:
        return {}
    return {
        "premise": index.get("premise", ""),
        "structure_type": index.get("structure_type", ""),
        "theme": index.get("theme", []),
        "act_count": index.get("act_count", 0),
    }


def _compact_characters(novel_dir: Path) -> list[dict[str, Any]]:
    profiles_dir = novel_dir / "characters" / "profiles"
    if not profiles_dir.is_dir():
        return []
    characters: list[dict[str, Any]] = []
    for path in sorted(profiles_dir.glob("*.yaml"))[:50]:
        profile = load_yaml(path)
        if not profile:
            continue
        characters.append(
            {
                "name": profile.get("name", ""),
                "role": profile.get("role", ""),
                "profile_level": profile.get("profile_level", ""),
                "narrative_function": profile.get("narrative_function", ""),
                "arc_summary": profile.get("arc_summary", ""),
            }
        )
    return characters


def _compact_worldbuilding(novel_dir: Path) -> list[dict[str, Any]]:
    index_path = novel_dir / "worldbuilding" / "_index.yaml"
    if not index_path.is_file():
        return []
    try:
        view = load_worldbuilding_view(novel_dir)
    except Exception:
        return []
    return [
        {
            "id": entity.id,
            "type": entity.type,
            "name": entity.name,
            "description": entity.description,
            "importance": entity.importance,
        }
        for entity in view.entities[:80]
    ]


__all__ = ["generate_work_profile"]
