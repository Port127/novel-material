"""项目配置与路径常量：支持通过环境变量自定义路径。"""
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from dotenv import load_dotenv

from novel_material.infra.yaml_io import load_yaml, save_yaml

load_dotenv()

# 使用包内相对路径计算项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# 配置目录
CONFIG_DIR = PROJECT_ROOT / "config"
SCHEMAS_DIR = DATA_DIR / "schemas"

# ──────────────────────────────────────────────
# settings.yaml 配置加载器
# ──────────────────────────────────────────────

_SETTINGS_FILE = CONFIG_DIR / "settings.yaml"
_settings_cache: dict | None = None
_settings_lock = Lock()


def _load_settings_yaml() -> dict:
    """加载 settings.yaml，返回所有键为字符串的平铺字典。"""
    if not _SETTINGS_FILE.exists():
        return {}
    return load_yaml(_SETTINGS_FILE)


def get_settings(*, reload: bool = False) -> dict:
    """获取合并后的配置：settings.yaml 为底，环境变量覆盖。

    缓存结果，避免重复读文件。调用 ``get_settings(reload=True)`` 可刷新。
    """
    global _settings_cache

    if reload:
        _settings_cache = None

    with _settings_lock:
        if _settings_cache is not None:
            return _settings_cache

        base = _load_settings_yaml()
        # 环境变量覆盖（只覆盖 settings.yaml 中已有的键）
        merged = {}
        for key, default in base.items():
            env_val = os.environ.get(key)
            if env_val is not None:
                # 保持类型：yaml 已解析的数字类型，env 是字符串
                if isinstance(default, int):
                    try:
                        env_val = int(env_val)
                    except ValueError:
                        pass
                elif isinstance(default, float):
                    try:
                        env_val = float(env_val)
                    except ValueError:
                        pass
                merged[key] = env_val
            else:
                merged[key] = default
        # 补充环境变量中独有但代码仍依赖的键（如 DATABASE_URL）
        for key in ("DATABASE_URL", "DB_USER", "DB_PASSWORD", "DB_NAME",
                     "PGADMIN_EMAIL", "PGADMIN_PASSWORD",
                     "LLM_API_KEY", "LLM_API_KEY_ALIYUN", "LLM_API_KEY_DEEPSEEK",
                     "LLM_API_KEY_OPENAI", "LLM_PROVIDER", "LLM_MODEL",
                     "LLM_BASE_URL", "LOG_LEVEL", "LOG_DIR"):
            if key not in merged:
                val = os.environ.get(key)
                if val is not None:
                    merged[key] = val

        _settings_cache = merged
        return _settings_cache


def clear_settings_cache() -> None:
    """清空配置缓存（测试用）。"""
    global _settings_cache
    with _settings_lock:
        _settings_cache = None


# ──────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────

_settings = get_settings()

NOVELS_DIR_ENV = _settings.get("NOVELS_DIR", "")
if NOVELS_DIR_ENV:
    NOVELS_DIR = Path(NOVELS_DIR_ENV)
else:
    NOVELS_DIR = DATA_DIR / "novels"

# 全局索引文件（可通过环境变量自定义）
GLOBAL_INDEX_ENV = _settings.get("GLOBAL_INDEX", "")
if GLOBAL_INDEX_ENV:
    INDEX_FILE = Path(GLOBAL_INDEX_ENV)
else:
    INDEX_FILE = DATA_DIR / "index.yaml"

# tags_view.yaml 仅为导出视图，不参与代码逻辑
TAGS_VIEW_FILE = DATA_DIR / "tags_view.yaml"

# ──────────────────────────────────────────────
# 统一 meta.yaml 状态管理
# ──────────────────────────────────────────────

VALID_STATUSES = {"raw", "clean", "evaluated", "analyzed", "finalized", "failed"}


def update_meta_status(material_id: str, status: str) -> None:
    """统一更新 meta.yaml 状态，做合法性检查。

    Args:
        material_id: 素材 ID
        status: 新状态值，必须在 VALID_STATUSES 中

    Raises:
        ValueError: 状态值不在合法集合中
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"非法状态: {status}，允许值: {sorted(VALID_STATUSES)}")

    meta_path = NOVELS_DIR / material_id / "meta.yaml"
    if not meta_path.exists():
        raise FileNotFoundError(f"meta.yaml 不存在: {meta_path}")

    meta = load_yaml(meta_path)

    meta["status"] = status
    meta["updated_at"] = datetime.now().isoformat()

    save_yaml(meta_path, meta)