"""日志服务：创建素材专属 logger。

核心功能：
- create_logger: 创建素材专属 logger

用于 ExecutionContext 统一携带 logger。
"""

import logging
from pathlib import Path

from novel_material.infra.logging_config import get_pipeline_logger


def create_logger(material_id: str, log_file: Path | str | None = None) -> logging.Logger:
    """创建素材专属 logger。

    Args:
        material_id: 素材 ID
        log_file: 日志文件路径（可选）

    Returns:
        logging.Logger: logger 实例
    """
    # 使用全局 pipeline logger，添加素材 ID 前缀
    logger = get_pipeline_logger()

    if log_file:
        log_file = Path(log_file)
        # 添加文件 handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            f"[{material_id}] %(asctime)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


__all__ = ["create_logger"]