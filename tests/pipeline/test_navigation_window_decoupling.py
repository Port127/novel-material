"""前置导航与滑动窗口解耦测试。"""

from novel_material.pipeline.analyze_context import load_optional_navigation_context


def test_missing_navigation_context_returns_diagnostic(tmp_path):
    context, diagnostics = load_optional_navigation_context(tmp_path)

    assert context == ""
    assert diagnostics == ("navigation_missing",)
