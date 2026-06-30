import numpy as np

from novel_material.infra.yaml_io import save_yaml
from novel_material.storage import embedding


def test_embed_worldbuilding_reads_layered_entities(
    tmp_path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    world_dir = novel / "worldbuilding" / "entities"
    world_dir.mkdir(parents=True)
    save_yaml(
        novel / "worldbuilding" / "_index.yaml",
        {"layout": "layered", "llm_success": True},
    )
    save_yaml(
        world_dir / "organization_x.yaml",
        {
            "id": "organization_x",
            "type": "organization",
            "name": "公司",
            "description": "创业组织",
            "properties": {"dimension_ids": ["business_rules"]},
            "importance": "primary",
            "evidence": [{"chapter": 3, "summary": "成立公司"}],
        },
    )
    observed_texts: list[str] = []

    monkeypatch.setattr(embedding, "NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        embedding,
        "load_embedding_config",
        lambda: {
            "embedding": {
                "provider": "fake",
                "model": "fake",
                "dimension": 3,
            }
        },
    )
    monkeypatch.setattr(
        embedding,
        "get_embedding",
        lambda text, _config: observed_texts.append(text) or [0.1, 0.2, 0.3],
    )

    embedding.embed_worldbuilding("nm_demo")

    data = np.load(novel / "worldbuilding" / "wb_embeddings.npz")
    assert data["keys"].tolist() == ["organization:公司"]
    assert "创业组织" in observed_texts[0]
    assert "business_rules" in observed_texts[0]
    assert "成立公司" in observed_texts[0]
