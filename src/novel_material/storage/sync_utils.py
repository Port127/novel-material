"""数据库同步公共函数：向量加载、异常类、数据库连接。

此模块包含 sync 流水线所需的公共函数和异常类，
供 sync_core.py 和各子模块使用。
"""
import os
import numpy as np
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from novel_material.infra.progress import get_pipeline_logger
from novel_material.storage.embedding_manifest import load_manifest, validate_vector

logger = get_pipeline_logger()
DATABASE_URL = os.getenv("DATABASE_URL")


def _load_embeddings_npz(
    npz_path: Path,
    *,
    return_manifest: bool = False,
):
    """从 NPZ 文件加载向量。

    支持两种格式：
    - 章节格式：chapters 数组（整数 key）
    - 通用格式：keys 数组（字符串 key）

    Args:
        npz_path: NPZ 文件路径

    Returns:
        dict: {key: embedding_list}
    """
    if not npz_path.exists():
        return ({}, None) if return_manifest else {}

    with np.load(str(npz_path)) as data:
        vectors_arr = data["vectors"]

        if "chapters" in data:
            chapters_arr = data["chapters"]
            embeddings = {
                str(int(ch)): vectors_arr[i].tolist()
                for i, ch in enumerate(chapters_arr)
            }
        elif "keys" in data:
            keys_arr = data["keys"]
            embeddings = {
                str(key): vectors_arr[i].tolist()
                for i, key in enumerate(keys_arr)
            }
        else:
            embeddings = {}

    manifest = load_manifest(npz_path)
    if manifest is None:
        logger.warning(f"Embedding 缓存 legacy-unverified: {npz_path}")
    else:
        for vector in embeddings.values():
            validate_vector(vector, manifest)

    if return_manifest:
        return embeddings, manifest
    return embeddings


class DatabaseConfigError(Exception):
    """数据库配置错误（如 DATABASE_URL 未设置）。"""
    pass


class QualityCheckError(Exception):
    """数据质量检查失败，可尝试修复后重试。

    Attributes:
        material_id: 素材 ID
        short_chapters: summary 长度不足的章节列表
        missing_chapters: 缺失的章节列表
        schema_error_chapters: schema 校验失败的章节列表
    """

    def __init__(
        self,
        material_id: str,
        short_chapters: list[int] = None,
        missing_chapters: list[int] = None,
        schema_error_chapters: list[int] = None
    ):
        self.material_id = material_id
        self.short_chapters = short_chapters or []
        self.missing_chapters = missing_chapters or []
        self.schema_error_chapters = schema_error_chapters or []

        # 构建消息
        msg = f"Schema 预检失败: {material_id}"
        if short_chapters:
            msg += f"（{len(short_chapters)} 章 summary 长度不足）"
        if missing_chapters:
            msg += f"（{len(missing_chapters)} 章缺失）"
        if schema_error_chapters:
            msg += f"（{len(schema_error_chapters)} 章 schema 错误）"
        super().__init__(msg)


class SchemaValidationError(Exception):
    """Schema 校验失败（非 summary 问题，无法自动修复）。"""
    pass


def get_db_connection():
    """获取数据库连接。

    Raises:
        DatabaseConfigError: DATABASE_URL 未设置
    """
    import psycopg2

    if not DATABASE_URL:
        raise DatabaseConfigError("DATABASE_URL 环境变量未设置")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


__all__ = [
    "_load_embeddings_npz",
    "DatabaseConfigError",
    "QualityCheckError",
    "SchemaValidationError",
    "get_db_connection",
    "DATABASE_URL",
    "logger",
]
