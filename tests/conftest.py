"""pytest fixtures for testing."""

import os
from pathlib import Path
import shutil
import tempfile

import pytest
import yaml


_TEST_RUNTIME_ROOT = Path(tempfile.mkdtemp(prefix="novel-material-tests-"))
_TEST_LOG_DIR = _TEST_RUNTIME_ROOT / "logs"
os.environ["LOG_DIR"] = str(_TEST_LOG_DIR)
os.environ["NOVEL_MATERIAL_TESTING"] = "1"


@pytest.fixture(scope="session")
def isolated_log_dir() -> Path:
    """返回与正式工作区隔离的测试日志目录。"""
    _TEST_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _TEST_LOG_DIR


def pytest_sessionfinish(session, exitstatus):
    """测试会话结束后清理临时运行目录。"""
    shutil.rmtree(_TEST_RUNTIME_ROOT, ignore_errors=True)


@pytest.fixture
def temp_novel_dir():
    """创建临时小说目录用于测试。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_chapter_text():
    """返回示例章节文本。"""
    return """第一章 开篇

这是第一章的内容。主角站在山顶。

第二章 发展

故事继续发展。主角遇到了新角色。

第三章 结局

故事结束，主角完成了目标。
"""


@pytest.fixture
def sample_ad_text():
    """返回包含广告的文本。"""
    return """第一章 开篇

这是正文内容。

本书来自www.example.com请记住我们的网址

更多小说尽在看书网

这是更多正文。
"""


@pytest.fixture
def sample_cn_chapter_text():
    """返回包含中文数字章节的文本。"""
    return """第一章 开篇

第一百二十三章 高潮

第一千零五章 结局
"""
