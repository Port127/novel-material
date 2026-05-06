"""项目路径常量：基于 __file__ 自动定位，与工作目录无关。"""
from datetime import datetime
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
NOVELS_DIR = DATA_DIR / "novels"
CONFIG_DIR = PROJECT_ROOT / "config"
SCHEMAS_DIR = DATA_DIR / "schemas"

# === TAGS_FILE 已废弃 ===
# 标签数据已迁移到数据库，不再使用文件
# TAGS_FILE = DATA_DIR / "tags.yaml"  # 已废弃

INDEX_FILE = DATA_DIR / "index.yaml"

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
