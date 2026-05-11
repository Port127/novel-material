"""日志系统全局配置。

所有日志行为通过环境变量控制：
- LOG_LEVEL: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- LOG_DIR: 日志目录

日志文件命名（进程级隔离）：
- pipeline: pipeline_{YYYY-MM-DD}_{PID}.log
- search: search_{YYYY-MM-DD}_{PID}.log
"""
import os
import sys
import time
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


# ============================================================================
# Pipeline 日志
# ============================================================================

_PIPELINE_HANDLER: logging.StreamHandler | None = None


def get_pipeline_logger() -> logging.Logger:
    """获取 pipeline logger（进程级隔离）。"""
    return _setup_pipeline_logger()


def _setup_pipeline_logger() -> logging.Logger:
    """配置 pipeline 日志记录器。"""
    global _PIPELINE_HANDLER
    logger = logging.getLogger("pipeline")
    if _PIPELINE_HANDLER is not None:
        return logger

    logger.setLevel(get_effective_level())
    log_dir = ensure_log_dir()

    # PID 隔离：每个进程独立日志文件
    # 文件名带时分秒，方便按创建顺序排列
    log_file = log_dir / f"pipeline_{time.strftime('%Y-%m-%d_%H-%M-%S')}_{os.getpid()}.log"
    # delay=True: 延迟创建文件，直到实际写入时才创建（避免空日志文件）
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a", delay=True)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    _PIPELINE_HANDLER = logging.StreamHandler(sys.stdout)
    _PIPELINE_HANDLER.setFormatter(logging.Formatter("%(message)s"))
    _PIPELINE_HANDLER.setLevel(get_effective_level())
    logger.addHandler(_PIPELINE_HANDLER)

    return logger


# ============================================================================
# Search 日志
# ============================================================================

_SEARCH_HANDLER: logging.StreamHandler | None = None


def get_search_logger() -> logging.Logger:
    """获取 search logger（独立日志文件，进程级隔离）。"""
    return _setup_search_logger()


def _setup_search_logger() -> logging.Logger:
    """配置 search 日志记录器。"""
    global _SEARCH_HANDLER
    logger = logging.getLogger("search")
    if _SEARCH_HANDLER is not None:
        return logger

    logger.setLevel(get_effective_level())
    log_dir = ensure_log_dir()

    log_file = log_dir / f"search_{time.strftime('%Y-%m-%d_%H-%M-%S')}_{os.getpid()}.log"
    # delay=True: 延迟创建文件，直到实际写入时才创建（避免空日志文件）
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a", delay=True)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    _SEARCH_HANDLER = logging.StreamHandler(sys.stdout)
    _SEARCH_HANDLER.setFormatter(logging.Formatter("%(message)s"))
    _SEARCH_HANDLER.setLevel(get_effective_level())
    logger.addHandler(_SEARCH_HANDLER)

    return logger


# ============================================================================
# Embedding 日志
# ============================================================================

_EMBEDDING_HANDLER: logging.StreamHandler | None = None


def get_embedding_logger() -> logging.Logger:
    """获取 embedding logger（独立日志文件，进程级隔离）。"""
    return _setup_embedding_logger()


def _setup_embedding_logger() -> logging.Logger:
    """配置 embedding 日志记录器。"""
    global _EMBEDDING_HANDLER
    logger = logging.getLogger("embedding")
    if _EMBEDDING_HANDLER is not None:
        return logger

    logger.setLevel(get_effective_level())
    log_dir = ensure_log_dir()

    log_file = log_dir / f"embedding_{time.strftime('%Y-%m-%d_%H-%M-%S')}_{os.getpid()}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="a", delay=True)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    _EMBEDDING_HANDLER = logging.StreamHandler(sys.stdout)
    _EMBEDDING_HANDLER.setFormatter(logging.Formatter("%(message)s"))
    _EMBEDDING_HANDLER.setLevel(get_effective_level())
    logger.addHandler(_EMBEDDING_HANDLER)

    return logger


# ============================================================================
# 控制台日志控制
# ============================================================================

def pause_console_logging() -> None:
    """暂停控制台日志输出（用于进度条显示期间）。

    临时移除 handler 以避免与 spinner 线程的 stdout 竞态条件。
    """
    global _PIPELINE_HANDLER
    if _PIPELINE_HANDLER is None:
        return
    logger = logging.getLogger("pipeline")
    if _PIPELINE_HANDLER in logger.handlers:
        logger.removeHandler(_PIPELINE_HANDLER)


def resume_console_logging() -> None:
    """恢复控制台日志输出。"""
    global _PIPELINE_HANDLER
    if _PIPELINE_HANDLER is None:
        return
    logger = logging.getLogger("pipeline")
    if _PIPELINE_HANDLER not in logger.handlers:
        logger.addHandler(_PIPELINE_HANDLER)