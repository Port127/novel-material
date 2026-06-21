"""中文词法检索文本构造测试。"""

from novel_material.search.text import build_search_text, tokenize_for_search


def test_tokenize_for_search_keeps_phrase_and_chinese_terms():
    """分词结果应同时保留原短语和关键中文词项。"""
    tokens = tokenize_for_search("主角在雨中告别导师")

    assert tokens.startswith("主角在雨中告别导师 ")
    assert "雨中" in tokens.split()
    assert "告别" in tokens.split()
    assert "导师" in tokens.split()


def test_build_search_text_ignores_empty_values_and_flattens_nested_parts():
    """检索文本应按输入顺序递归展开列表和字典值。"""
    text = build_search_text(
        "第七章",
        None,
        ["雨夜", "告别"],
        {"hook": "悬念", "empty": ""},
    )

    assert text == "第七章 雨夜 告别 悬念"
