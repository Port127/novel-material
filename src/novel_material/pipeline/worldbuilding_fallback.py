"""Conservative worldbuilding fallback from chapter-level statistics."""

from __future__ import annotations

from typing import Any


def build_stats_seeded_entities(
    stats: dict[str, dict[str, int]],
    *,
    min_count: int = 5,
) -> list[dict[str, Any]]:
    entities: list[dict[str, Any]] = []
    type_map = {"organizations": "organization", "locations": "location"}
    for bucket, entity_type in type_map.items():
        sorted_stats = sorted(
            stats.get(bucket, {}).items(),
            key=lambda item: (-item[1], item[0]),
        )
        for name, count in sorted_stats:
            if count < min_count:
                continue
            entities.append(
                {
                    "type": entity_type,
                    "name": name,
                    "description": f"从章级分析统计生成的基础实体，出现 {count} 次，待 LLM 补全。",
                    "importance": "primary" if count >= 10 else "secondary",
                    "source_quality": "stats_seeded",
                    "confidence": 0.45,
                    "evidence": [
                        {
                            "chapter": 1,
                            "basis": "fact",
                            "summary": "章级分析统计中高频出现该实体。",
                        }
                    ],
                }
            )
    return entities


__all__ = ["build_stats_seeded_entities"]
