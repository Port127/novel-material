"""chapter_insights YAML 搜索测试。"""

from pathlib import Path

from novel_material.infra.yaml_io import save_yaml
from novel_material.search.insight import search_insights


def test_search_insights_matches_common_and_genre_fields(tmp_path: Path):
    material_dir = tmp_path / "nm_demo"
    insights_dir = material_dir / "chapter_insights"
    insights_dir.mkdir(parents=True)
    save_yaml(
        insights_dir / "0001.yaml",
        {
            "chapter": 1,
            "title": "第1章 开篇",
            "profiles": ["common", "xuanhuan"],
            "common": {
                "conflict": "主角被家族压制。",
                "reader_hook": "戒指是否藏有传承。",
                "writing_takeaway": "先压低主角处境，再用戒指线索制造期待。",
            },
            "genre": {
                "resource_gain": "获得戒指传承线索。",
            },
        },
    )

    results = search_insights("戒指", novels_dir=tmp_path)

    assert [result.model_dump() for result in results] == [
        {
            "result_id": "insight:nm_demo:1",
            "document_type": "insight",
            "material_id": "nm_demo",
            "entity_id": None,
            "chapter": 1,
            "title": "第1章 开篇",
            "summary": "先压低主角处境，再用戒指线索制造期待。",
            "content": "",
            "metadata": {
                "profiles": ["common", "xuanhuan"],
                "writing_takeaway": "先压低主角处境，再用戒指线索制造期待。",
            },
            "source": None,
            "neighbors": None,
            "scores": {},
            "matched_fields": ["common.reader_hook", "common.writing_takeaway", "genre.resource_gain"],
            "final_score": None,
            "rank_reason": "",
        }
    ]
