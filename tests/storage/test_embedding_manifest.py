"""Embedding provenance 与维度校验测试。"""

from pathlib import Path
import logging

import numpy as np
import pytest

from novel_material.storage.embedding_manifest import (
    EmbeddingManifest,
    load_manifest,
    manifest_from_config,
    manifest_path,
    save_manifest,
    validate_vector,
)
from novel_material.infra.embedding import get_embedding
from novel_material.storage.embedding import (
    _save_chapter_embeddings,
    _save_embeddings,
)
from novel_material.storage.sync_utils import _load_embeddings_npz


def _manifest() -> EmbeddingManifest:
    return EmbeddingManifest(
        provider="ollama",
        model="qwen3-embedding",
        dimension=4096,
        text_version="chapter-summary-v1",
    )


def test_validate_vector_rejects_wrong_dimension():
    """实际向量维度必须与 manifest 一致。"""
    with pytest.raises(ValueError, match="期望 4096.*实际 3"):
        validate_vector([0.1, 0.2, 0.3], _manifest())


def test_manifest_uses_npz_stem_and_round_trips(tmp_path: Path):
    """manifest 应与 NPZ 同目录同名并可无损读取。"""
    npz_path = tmp_path / "chapter_embeddings.npz"
    manifest = _manifest()

    save_manifest(npz_path, manifest)

    expected_path = tmp_path / "chapter_embeddings.manifest.yaml"
    assert manifest_path(npz_path) == expected_path
    assert expected_path.exists()
    assert load_manifest(npz_path) == manifest


def test_get_embedding_validates_configured_dimension(monkeypatch):
    """Provider 返回错误维度时应在 API 边界立即失败。"""

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[0.1, 0.2]]}

    monkeypatch.setattr("requests.post", lambda *_args, **_kwargs: FakeResponse())
    config = {
        "embedding": {
            "provider": "ollama",
            "model": "qwen3-embedding",
            "dimension": 3,
            "base_url": "http://localhost:11434",
            "api_key": "",
        }
    }

    with pytest.raises(ValueError, match="期望 3.*实际 2"):
        get_embedding("测试文本", config)


@pytest.mark.parametrize(
    ("filename", "saver", "embeddings"),
    [
        ("chapter_embeddings.npz", _save_chapter_embeddings, {1: [0.1, 0.2, 0.3]}),
        ("character_embeddings.npz", _save_embeddings, {"林师": [0.1, 0.2, 0.3]}),
    ],
)
def test_npz_savers_write_manifest(filename, saver, embeddings, tmp_path):
    """两种 NPZ 格式保存时都必须同步写入 provenance。"""
    config = {
        "embedding": {
            "provider": "ollama",
            "model": "qwen3-embedding",
            "dimension": 3,
        }
    }
    manifest = manifest_from_config(config, "chapter-summary-v1")
    npz_path = tmp_path / filename

    saver(npz_path, embeddings, manifest=manifest)

    assert npz_path.exists()
    assert load_manifest(npz_path) == manifest


def test_sync_loader_rejects_vector_that_conflicts_with_manifest(tmp_path):
    """同步前必须拒绝与 manifest 维度冲突的缓存。"""
    npz_path = tmp_path / "chapter_embeddings.npz"
    np.savez_compressed(
        npz_path,
        chapters=np.array([1], dtype=np.int32),
        vectors=np.array([[0.1, 0.2, 0.3]], dtype=np.float32),
    )
    save_manifest(
        npz_path,
        EmbeddingManifest(
            provider="ollama",
            model="qwen3-embedding",
            dimension=4,
            text_version="chapter-summary-v1",
        ),
    )

    with pytest.raises(ValueError, match="期望 4.*实际 3"):
        _load_embeddings_npz(npz_path)


def test_sync_loader_marks_legacy_npz_unverified(tmp_path, caplog):
    """无 manifest 的旧缓存应可读，但必须留下未验证日志。"""
    npz_path = tmp_path / "chapter_embeddings.npz"
    np.savez_compressed(
        npz_path,
        chapters=np.array([1], dtype=np.int32),
        vectors=np.array([[0.1, 0.2, 0.3]], dtype=np.float32),
    )

    with caplog.at_level(logging.WARNING):
        embeddings = _load_embeddings_npz(npz_path)

    assert list(embeddings) == ["1"]
    assert "legacy-unverified" in caplog.text


def test_sync_loader_can_return_manifest(tmp_path):
    """评测或同步调用方可选择同时读取 provenance。"""
    npz_path = tmp_path / "character_embeddings.npz"
    manifest = EmbeddingManifest(
        provider="ollama",
        model="qwen3-embedding",
        dimension=3,
        text_version="character-profile-v1",
    )
    _save_embeddings(
        npz_path,
        {"林师": [0.1, 0.2, 0.3]},
        manifest=manifest,
    )

    embeddings, loaded_manifest = _load_embeddings_npz(
        npz_path,
        return_manifest=True,
    )

    assert list(embeddings) == ["林师"]
    assert loaded_manifest == manifest
