"""日志系统全局配置。

所有日志行为通过环境变量控制：
- LOG_LEVEL: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- LOG_DIR: 日志目录
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 环境变量配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))

# 级别映射
LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def get_effective_level() -> int:
    """获取有效日志级别（从环境变量或默认 INFO）。"""
    return LEVEL_MAP.get(LOG_LEVEL.upper(), logging.INFO)


def ensure_log_dir() -> Path:
    """确保日志目录存在，返回路径。"""
    # LOG_DIR 可能是相对路径，需要相对于项目根目录解析
    if not LOG_DIR.is_absolute():
        from novel_material.infra.config import PROJECT_ROOT
        log_dir = PROJECT_ROOT / LOG_DIR
    else:
        log_dir = LOG_DIR

    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_log_level_name() -> str:
    """获取日志级别名称（用于显示）。"""
    return LOG_LEVEL.upper()