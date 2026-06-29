"""主要人物完整小传响应规范化。"""

from __future__ import annotations

from typing import Any

from novel_material.infra.llm_contracts import (
    LLMResponseContractError,
    require_integer,
    require_mapping,
    require_mapping_list,
    require_number,
    require_string,
    require_string_list,
)


_REQUIRED_STRING_FIELDS = (
    "identity",
    "life_summary",
    "external_goal",
    "internal_need",
    "fear",
    "fatal_flaw",
    "contradiction",
    "speech_style",
    "description",
    "arc_summary",
    "narrative_function",
)


def normalize_biography_response(
    payload: object,
    candidate_names: set[str],
) -> list[dict[str, Any]]:
    """规范化主要人物完整小传响应。

    返回结果保留旧消费字段，同时补齐完整小传标记：
    ``profile_level=full`` 与 ``biography_complete=True``。
    """
    raw = (
        payload
        if isinstance(payload, list)
        else require_mapping(payload, "characters").get("characters")
    )
    characters = require_mapping_list(raw, "characters")
    normalized: list[dict[str, Any]] = []

    for index, character in enumerate(characters):
        path = f"characters[{index}]"
        profile = dict(character)
        name = require_string(profile.get("name"), f"{path}.name")
        if name not in candidate_names:
            raise LLMResponseContractError(
                f"{path}.name",
                "候选名单中的字符串",
                name,
            )

        profile["name"] = name
        profile["role"] = require_string(profile.get("role"), f"{path}.role")
        profile["arc_stages"] = _normalize_arc_stages(
            profile.get("arc_stages"),
            f"{path}.arc_stages",
        )
        profile["relationships"] = _normalize_relationships(
            profile.get("relationships"),
            f"{path}.relationships",
        )
        profile["key_scenes"] = _normalize_key_scenes(
            profile.get("key_scenes"),
            f"{path}.key_scenes",
        )
        profile["craft_notes"] = _normalize_craft_notes(
            profile.get("craft_notes"),
            f"{path}.craft_notes",
        )
        profile["psychology"] = require_mapping(
            profile.get("psychology"),
            f"{path}.psychology",
        )
        profile["key_events"] = _normalize_key_events(
            profile.get("key_events"),
            f"{path}.key_events",
        )
        profile["habits"] = require_string_list(
            profile.get("habits"),
            f"{path}.habits",
        )
        profile["interaction_patterns"] = require_string_list(
            profile.get("interaction_patterns"),
            f"{path}.interaction_patterns",
        )
        for field in _REQUIRED_STRING_FIELDS:
            profile[field] = require_string(profile.get(field), f"{path}.{field}")

        profile["archetype"] = require_string(
            profile.get("archetype"),
            f"{path}.archetype",
        )
        profile["moral_spectrum"] = require_string(
            profile.get("moral_spectrum"),
            f"{path}.moral_spectrum",
        )
        profile["first_appearance_chapter"] = require_integer(
            profile.get("first_appearance_chapter"),
            f"{path}.first_appearance_chapter",
        )
        profile["confidence"] = require_number(
            profile.get("confidence"),
            f"{path}.confidence",
        )
        profile["basis"] = _require_basis(profile.get("basis"), f"{path}.basis")
        profile["profile_level"] = "full"
        profile["biography_complete"] = True
        normalized.append(profile)

    return normalized


def _normalize_arc_stages(value: object, path: str) -> list[dict[str, Any]]:
    stages = require_mapping_list(value, path)
    for index, stage in enumerate(stages):
        item_path = f"{path}[{index}]"
        stage["stage"] = require_string(stage.get("stage"), f"{item_path}.stage")
        stage["change"] = require_string(stage.get("change"), f"{item_path}.change")
        stage["evidence"] = require_mapping(
            stage.get("evidence"),
            f"{item_path}.evidence",
        )
    return stages


def _normalize_relationships(value: object, path: str) -> list[dict[str, Any]]:
    relationships = require_mapping_list(value, path)
    for index, relationship in enumerate(relationships):
        item_path = f"{path}[{index}]"
        relationship["character"] = require_string(
            relationship.get("character"),
            f"{item_path}.character",
        )
        dynamic = relationship.get("dynamic", relationship.get("relationship"))
        dynamic_text = require_string(dynamic, f"{item_path}.dynamic")
        relationship["dynamic"] = dynamic_text
        relationship.setdefault("relationship", dynamic_text)
        if relationship.get("evidence") is not None:
            relationship["evidence"] = require_mapping(
                relationship.get("evidence"),
                f"{item_path}.evidence",
            )
    return relationships


def _normalize_key_scenes(value: object, path: str) -> list[dict[str, Any]]:
    scenes = require_mapping_list(value, path)
    for index, scene in enumerate(scenes):
        item_path = f"{path}[{index}]"
        scene["chapter"] = require_integer(scene.get("chapter"), f"{item_path}.chapter")
        scene["event"] = require_string(scene.get("event"), f"{item_path}.event")
        scene["function"] = require_string(
            scene.get("function"),
            f"{item_path}.function",
        )
    return scenes


def _normalize_craft_notes(value: object, path: str) -> list[dict[str, Any]]:
    notes = require_mapping_list(value, path)
    for index, note in enumerate(notes):
        item_path = f"{path}[{index}]"
        note["technique"] = require_string(
            note.get("technique"),
            f"{item_path}.technique",
        )
        note["boundary"] = require_string(
            note.get("boundary"),
            f"{item_path}.boundary",
        )
    return notes


def _normalize_key_events(value: object, path: str) -> list[dict[str, Any]]:
    events = require_mapping_list(value, path)
    for index, event in enumerate(events):
        item_path = f"{path}[{index}]"
        event["chapter"] = require_integer(event.get("chapter"), f"{item_path}.chapter")
        event["description"] = require_string(
            event.get("description"),
            f"{item_path}.description",
        )
    return events


def _require_basis(value: object, path: str) -> str:
    basis = require_string(value, path)
    if basis not in {"fact", "inference"}:
        raise LLMResponseContractError(path, "fact 或 inference", value)
    return basis


__all__ = ["normalize_biography_response"]
