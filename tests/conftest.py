"""pytest fixtures for testing."""
import pytest
from pathlib import Path
import tempfile
import yaml


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