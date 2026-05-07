"""项目路径常量：支持通过环境变量自定义路径。"""
import os
from datetime import datetime
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# 小说存储目录（可通过环境变量自定义）
NOVELS_DIR_ENV = os.getenv("NOVELS_DIR")
if NOVELS_DIR_ENV:
    NOVELS_DIR = Path(NOVELS_DIR_ENV)
else:
    NOVELS_DIR = DATA_DIR / "novels"

# 配置目录
CONFIG_DIR = PROJECT_ROOT / "config"
SCHEMAS_DIR = DATA_DIR / "schemas"

# 全局索引文件（可通过环境变量自定义）
GLOBAL_INDEX_ENV = os.getenv("GLOBAL_INDEX")
if GLOBAL_INDEX_ENV:
    INDEX_FILE = Path(GLOBAL_INDEX_ENV)
else:
    INDEX_FILE = DATA_DIR / "index.yaml"

# TAGS_FILE 已废弃（标签数据已迁移到数据库）
# TAGS_FILE 配置项保留在 .env 但不再使用

# tags_view.yaml 仅为导出视图，不参与代码逻辑
TAGS_VIEW_FILE = DATA_DIR / "tags_view.yaml"

# ──────────────────────────────────────────────
# 统一 meta.yaml 状态管理
# ──────────────────────────────────────────────

VALID_STATUSES = {"raw", "clean", "analyzed", "indexed", "failed"}


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

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    meta["status"] = status
    meta["updated_at"] = datetime.now().isoformat()

    with open(meta_path, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)
