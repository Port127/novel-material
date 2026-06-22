"""测试运行时副作用隔离。"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def test_test_suite_uses_isolated_log_dir(isolated_log_dir: Path):
    assert isolated_log_dir.exists()
    assert isolated_log_dir != ROOT / "logs"
    assert isolated_log_dir.is_relative_to(Path(tempfile.gettempdir()))
    assert os.environ["LOG_DIR"] == str(isolated_log_dir)
    assert os.environ["NOVEL_MATERIAL_TESTING"] == "1"
