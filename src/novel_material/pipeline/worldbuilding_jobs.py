"""Worldbuilding dimension job construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorldbuildingJob:
    dimension_id: str
    dimension_name: str
    context_text: str
    context_label: str


def build_worldbuilding_jobs(
    dimensions: list[dict[str, Any]],
    *,
    context_text: str,
    context_label: str,
) -> list[WorldbuildingJob]:
    jobs: list[WorldbuildingJob] = []
    for dimension in dimensions:
        if dimension.get("applicability") != "applicable":
            continue
        jobs.append(
            WorldbuildingJob(
                dimension_id=str(dimension.get("id") or ""),
                dimension_name=str(dimension.get("name") or dimension.get("id") or ""),
                context_text=context_text,
                context_label=context_label,
            )
        )
    return [job for job in jobs if job.dimension_id]


__all__ = ["WorldbuildingJob", "build_worldbuilding_jobs"]
