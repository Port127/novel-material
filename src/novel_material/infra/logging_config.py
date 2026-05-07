"""日志系统全局配置。

所有日志行为通过环境变量控制：
- LOG_LEVEL: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
- LOG_DIR: 日志目录
- LOG_MAX_FILES: 保留日志文件数量
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 环境变量配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_MAX_FILES = int(os.getenv("LOG_MAX_FILES", "100"))

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


def cleanup_old_logs(max_files: int = None) -> int:
    """清理旧日志文件，保留最新的 max_files 个。

    Args:
        max_files: 保留数量，默认使用 LOG_MAX_FILES
                   设为 0 表示禁用清理

    Returns:
        删除的文件数量
    """
    max_files = max_files or LOG_MAX_FILES

    # 保护：max_files=0 表示禁用清理，不删除任何文件
    if max_files <= 0:
        return 0

    log_dir = ensure_log_dir()

    # 按修改时间排序，最新的在前
    log_files = []
    for f in log_dir.glob("pipeline_*.log"):
        try:
            log_files.append((f, f.stat().st_mtime))
        except OSError:
            pass  # 文件可能在 glob 后被删除

    log_files.sort(key=lambda x: x[1], reverse=True)
    files_to_delete = [f[0] for f in log_files[max_files:]]

    deleted = 0
    for old_file in files_to_delete:
            try:
                old_file.unlink()
                deleted += 1
            except Exception:
                pass  # 清理失败不影响运行

    return deleted


def get_log_level_name() -> str:
    """获取日志级别名称（用于显示）。"""
    return LOG_LEVEL.upper()