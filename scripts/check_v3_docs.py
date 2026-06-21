#!/usr/bin/env python3
"""检查 Novel Material V3 现行文档的一致性。"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_DOCUMENTS = [
    Path("README.md"),
    Path("ARCHITECTURE.md"),
    Path("docs/REQUIREMENTS.md"),
    Path("docs/USER_MANUAL.md"),
    Path("docs/README.md"),
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("pyproject.toml"),
    Path("src/novel_material/storage/schema.sql"),
]
MARKDOWN_DOCUMENTS = [path for path in CURRENT_DOCUMENTS if path.suffix == ".md"]
FORBIDDEN = {
    "Novel Material V2": "仍包含 V2 项目标识",
    'version = "2.0.0"': "仍包含 2.0.0 包版本",
    "GENRE_AWARE_ANALYSIS.md": "仍链接已合并的题材分析指南",
    "当前主 CLI 暴露五类": "仍包含过期的五类检索说明",
    "当前章节搜索默认是关键词匹配": "仍包含过期的单路检索说明",
    "还不是混合检索": "仍包含过期的检索架构说明",
    "当前未暴露 CLI": "仍包含过期的细纲 CLI 说明",
}
SEARCH_COMMANDS = (
    "chapter",
    "event",
    "outline",
    "character",
    "world",
    "detail",
    "insight",
)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def check_current_docs(root: Path, documents: list[Path]) -> list[str]:
    """检查缺失文件及禁止出现的过期文本。"""
    issues: list[str] = []
    for relative in documents:
        path = root / relative
        if not path.is_file():
            issues.append(f"{relative}: 现行文档不存在")
            continue
        text = path.read_text(encoding="utf-8")
        for pattern, message in FORBIDDEN.items():
            if pattern in text:
                issues.append(f"{relative}: {message}: {pattern}")
    return issues


def check_markdown_links(root: Path, documents: list[Path]) -> list[str]:
    """检查现行 Markdown 中的本地相对链接。"""
    issues: list[str] = []
    for relative in documents:
        path = root / relative
        if not path.is_file():
            continue
        for raw_target in LINK_PATTERN.findall(path.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith(("mailto:", "/")):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                issues.append(f"{relative}: 链接目标不存在: {target}")
    return issues


def normalize_agent_guide(text: str) -> str:
    """忽略允许存在的宿主 Skill 入口差异。"""
    return text.replace(".agents/skills", "{skills_dir}").replace(
        ".claude/skills", "{skills_dir}"
    )


def check_agent_guides(root: Path) -> list[str]:
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8")
    if normalize_agent_guide(agents) != normalize_agent_guide(claude):
        return ["AGENTS.md 与 CLAUDE.md 存在超出 Skills 路径的内容差异"]
    return []


def check_search_commands(root: Path) -> list[str]:
    manual = (root / "docs/USER_MANUAL.md").read_text(encoding="utf-8")
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    issues: list[str] = []
    for command in SEARCH_COMMANDS:
        needle = f"nm search {command}"
        if needle not in manual:
            issues.append(f"docs/USER_MANUAL.md: 缺少公开命令: {needle}")
        if needle not in agents:
            issues.append(f"AGENTS.md: 缺少公开命令: {needle}")
    return issues


def check_repository(root: Path = PROJECT_ROOT) -> list[str]:
    issues = check_current_docs(root, CURRENT_DOCUMENTS)
    issues.extend(check_markdown_links(root, MARKDOWN_DOCUMENTS))
    if (root / "AGENTS.md").is_file() and (root / "CLAUDE.md").is_file():
        issues.extend(check_agent_guides(root))
        issues.extend(check_search_commands(root))
    return issues


def main() -> int:
    issues = check_repository()
    for issue in issues:
        print(issue)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
