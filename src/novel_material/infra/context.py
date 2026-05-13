"""执行上下文：统一携带 logger、paths、progress、config。

核心功能：
- ExecutionContext: 执行上下文类
- ExecutionContext.create: 创建上下文实例

用于统一传递流水线执行所需的全部依赖。
"""

import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable

from novel_material.infra.logging_service import create_logger
from novel_material.infra.path_service import PathService
from novel_material.infra.progress_manager import ProgressManager
from novel_material.infra.llm import load_config


@dataclass
class ExecutionContext:
    """执行上下文，统一携带流水线执行所需的全部依赖。"""
    material_id: str
    logger: logging.Logger
    paths: PathService
    progress: ProgressManager
    config: dict

    @classmethod
    def create(
        cls,
        material_id: str,
        log_file: Path | str | None = None,
        progress_callback: Callable[[int, int, int, str], None] | None = None,
        config: dict | None = None,
        provider: str | None = None,
    ) -> "ExecutionContext":
        """创建执行上下文实例。

        Args:
            material_id: 素材 ID
            log_file: 日志文件路径（可选）
            progress_callback: 进度回调函数（可选）
            config: LLM 配置（可选，不指定则从 load_config 加载）
            provider: LLM 服务商名称（可选）

        Returns:
            ExecutionContext: 上下文实例
        """
        logger = create_logger(material_id, log_file)
        paths = PathService()
        progress = ProgressManager(update_callback=progress_callback)

        # 加载配置
        if config is None:
            effective_config = load_config(provider)
        else:
            effective_config = config

        return cls(
            material_id=material_id,
            logger=logger,
            paths=paths,
            progress=progress,
            config=effective_config,
        )

    def info(self, msg: str) -> None:
        """便捷日志方法。"""
        self.logger.info(f"[{self.material_id}] {msg}")

    def warning(self, msg: str) -> None:
        """便捷日志方法。"""
        self.logger.warning(f"[{self.material_id}] {msg}")

    def error(self, msg: str) -> None:
        """便捷日志方法。"""
        self.logger.error(f"[{self.material_id}] {msg}")

    def debug(self, msg: str) -> None:
        """便捷日志方法。"""
        self.logger.debug(f"[{self.material_id}] {msg}")

    def novel_dir(self) -> Path:
        """便捷路径方法：素材目录。"""
        return self.paths.novel_dir(self.material_id)

    def meta_path(self) -> Path:
        """便捷路径方法：meta.yaml。"""
        return self.paths.meta_path(self.material_id)

    def chapters_path(self) -> Path:
        """便捷路径方法：chapters.yaml。"""
        return self.paths.chapters_path(self.material_id)

    def chapters_dir(self) -> Path:
        """便捷路径方法：chapters/ 目录。"""
        return self.paths.chapters_dir(self.material_id)


__all__ = ["ExecutionContext"]