from pathlib import Path

from scripts.check_v3_docs import (
    check_current_docs,
    check_markdown_links,
    normalize_agent_guide,
)


def test_check_rejects_v2_and_deleted_guide_links(tmp_path):
    document = tmp_path / "README.md"
    document.write_text(
        "# Novel Material V2\n[旧指南](docs/GENRE_AWARE_ANALYSIS.md)\n",
        encoding="utf-8",
    )

    issues = check_current_docs(tmp_path, [Path("README.md")])

    assert any("V2" in issue for issue in issues)
    assert any("GENRE_AWARE_ANALYSIS" in issue for issue in issues)


def test_check_accepts_v3_document(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Novel Material V3\n",
        encoding="utf-8",
    )

    assert check_current_docs(tmp_path, [Path("README.md")]) == []


def test_markdown_link_check_reports_missing_relative_target(tmp_path):
    (tmp_path / "README.md").write_text(
        "[不存在](docs/missing.md)\n",
        encoding="utf-8",
    )

    issues = check_markdown_links(tmp_path, [Path("README.md")])

    assert issues == ["README.md: 链接目标不存在: docs/missing.md"]


def test_agent_guide_normalization_only_ignores_skills_directory():
    agents = "入口 `.agents/skills/`，默认 quality。"
    claude = "入口 `.claude/skills/`，默认 quality。"

    assert normalize_agent_guide(agents) == normalize_agent_guide(claude)
    assert normalize_agent_guide(agents) != normalize_agent_guide(
        "入口 `.claude/skills/`，默认 exact。"
    )
