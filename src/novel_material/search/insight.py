"""Search chapter_insights YAML files without requiring PostgreSQL."""

from __future__ import annotations

from pathlib import Path

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml
from novel_material.search.models import SearchResult

COMMON_SEARCH_FIELDS = ("conflict", "reader_hook", "writing_takeaway")


def _matches(query: str, value: object) -> bool:
    return isinstance(value, str) and query in value


def _matched_fields(query: str, insight: dict) -> list[str]:
    matched: list[str] = []
    common = insight.get("common")
    if isinstance(common, dict):
        for field in COMMON_SEARCH_FIELDS:
            if _matches(query, common.get(field)):
                matched.append(f"common.{field}")

    genre = insight.get("genre")
    if isinstance(genre, dict):
        for field, value in genre.items():
            if _matches(query, value):
                matched.append(f"genre.{field}")

    return matched


def search_insights(
    query: str,
    limit: int = 10,
    novels_dir: Path | None = None,
) -> list[SearchResult]:
    """Search generated chapter insights by simple YAML field scanning."""
    base_dir = novels_dir or NOVELS_DIR
    results: list[SearchResult] = []

    if not base_dir.exists():
        return results

    for material_dir in sorted(base_dir.iterdir()):
        if not material_dir.is_dir():
            continue
        insights_dir = material_dir / "chapter_insights"
        if not insights_dir.exists():
            continue

        for path in sorted(insights_dir.glob("*.yaml")):
            insight = load_yaml(path)
            matched_fields = _matched_fields(query, insight)
            if not matched_fields:
                continue
            common = insight.get("common") if isinstance(insight.get("common"), dict) else {}
            chapter = insight.get("chapter")
            writing_takeaway = common.get("writing_takeaway", "")
            results.append(SearchResult(
                result_id=f"insight:{material_dir.name}:{chapter}",
                document_type="insight",
                material_id=material_dir.name,
                chapter=chapter,
                title=insight.get("title", ""),
                summary=writing_takeaway,
                metadata={
                    "profiles": insight.get("profiles", []),
                    "writing_takeaway": writing_takeaway,
                },
                matched_fields=matched_fields,
            ))
            if len(results) >= limit:
                return results

    return results
