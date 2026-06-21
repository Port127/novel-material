"""Embedding 文件的 provenance manifest 与维度校验。"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
import yaml


class EmbeddingManifest(BaseModel):
    """描述一组向量的来源、维度与文本构造版本。"""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    dimension: int = Field(gt=0)
    text_version: str = Field(min_length=1)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


def manifest_from_config(
    config: dict[str, Any],
    text_version: str,
) -> EmbeddingManifest:
    """使用 embedding 配置和文本构造版本创建 manifest。"""
    embedding = config["embedding"]
    return EmbeddingManifest(
        provider=embedding["provider"],
        model=embedding["model"],
        dimension=embedding["dimension"],
        text_version=text_version,
    )


def manifest_path(npz_path: Path) -> Path:
    """返回与 NPZ 同目录同名的 manifest 路径。"""
    return npz_path.with_suffix(".manifest.yaml")


def save_manifest(npz_path: Path, manifest: EmbeddingManifest) -> None:
    """将 manifest 写入 NPZ 旁路 YAML。"""
    path = manifest_path(npz_path)
    path.write_text(
        yaml.safe_dump(
            manifest.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def load_manifest(npz_path: Path) -> EmbeddingManifest | None:
    """读取 manifest；旧 NPZ 没有旁路文件时返回 None。"""
    path = manifest_path(npz_path)
    if not path.exists():
        return None
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return EmbeddingManifest.model_validate(payload)


def validate_vector(vector: Any, manifest: EmbeddingManifest) -> Any:
    """拒绝与 manifest 声明维度不一致的向量。"""
    actual_dimension = len(vector)
    if actual_dimension != manifest.dimension:
        raise ValueError(
            f"Embedding 维度不一致：期望 {manifest.dimension}，"
            f"实际 {actual_dimension}"
        )
    return vector
