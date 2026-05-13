"""路径服务：统一管理小说素材目录路径。

核心功能：
- novel_dir: 素材目录路径
- meta_path: meta.yaml 路径
- chapters_path: chapters.yaml 路径
- chapters_dir: chapters/ 目录
- outline_dir: outline/ 目录
- characters_dir: characters/ 目录
- evaluation_path: evaluation.yaml 路径
"""

from pathlib import Path

from novel_material.infra.config import NOVELS_DIR


class PathService:
    """路径服务类，统一管理素材目录路径。"""

    def __init__(self, novels_dir: Path | None = None):
        """初始化路径服务。

        Args:
            novels_dir: 小说根目录（可选，默认使用 NOVELS_DIR）
        """
        self._novels_dir = novels_dir or NOVELS_DIR

    def novel_dir(self, material_id: str) -> Path:
        """素材目录路径。

        Args:
            material_id: 素材 ID

        Returns:
            Path: 素材目录
        """
        return self._novels_dir / material_id

    def meta_path(self, material_id: str) -> Path:
        """meta.yaml 路径。

        Args:
            material_id: 素材 ID

        Returns:
            Path: meta.yaml 文件路径
        """
        return self.novel_dir(material_id) / "meta.yaml"

    def chapters_path(self, material_id: str) -> Path:
        """chapters.yaml 路径。

        Args:
            material_id: 素材 ID

        Returns:
            Path: chapters.yaml 文件路径
        """
        return self.novel_dir(material_id) / "chapters.yaml"

    def chapters_dir(self, material_id: str) -> Path:
        """chapters/ 目录。

        Args:
            material_id: 素材 ID

        Returns:
            Path: chapters/ 目录
        """
        return self.novel_dir(material_id) / "chapters"

    def chapter_index_path(self, material_id: str) -> Path:
        """chapter_index.yaml 路径。

        Args:
            material_id: 素材 ID

        Returns:
            Path: chapter_index.yaml 文件路径
        """
        return self.novel_dir(material_id) / "chapter_index.yaml"

    def source_path(self, material_id: str) -> Path:
        """source.txt 路径。

        Args:
            material_id: 素材 ID

        Returns:
            Path: source.txt 文件路径
        """
        return self.novel_dir(material_id) / "source.txt"

    def outline_dir(self, material_id: str) -> Path:
        """outline/ 目录。

        Args:
            material_id: 素材 ID

        Returns:
            Path: outline/ 目录
        """
        return self.novel_dir(material_id) / "outline"

    def characters_dir(self, material_id: str) -> Path:
        """characters/ 目录。

        Args:
            material_id: 素材 ID

        Returns:
            Path: characters/ 目录
        """
        return self.novel_dir(material_id) / "characters"

    def evaluation_path(self, material_id: str) -> Path:
        """evaluation.yaml 路径。

        Args:
            material_id: 素材 ID

        Returns:
            Path: evaluation.yaml 文件路径
        """
        return self.novel_dir(material_id) / "evaluation.yaml"

    def worldbuilding_dir(self, material_id: str) -> Path:
        """worldbuilding/ 目录。

        Args:
            material_id: 素材 ID

        Returns:
            Path: worldbuilding/ 目录
        """
        return self.novel_dir(material_id) / "worldbuilding"

    def tags_path(self, material_id: str) -> Path:
        """tags.yaml 路径。

        Args:
            material_id: 素材 ID

        Returns:
            Path: tags.yaml 文件路径
        """
        return self.novel_dir(material_id) / "tags.yaml"


__all__ = ["PathService"]