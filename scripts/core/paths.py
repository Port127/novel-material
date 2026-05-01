"""项目路径常量：基于 __file__ 自动定位，与工作目录无关。"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
NOVELS_DIR = DATA_DIR / "novels"
CONFIG_DIR = PROJECT_ROOT / "config"
SCHEMAS_DIR = DATA_DIR / "schemas"
TAGS_FILE = DATA_DIR / "tags.yaml"
INDEX_FILE = DATA_DIR / "index.yaml"
