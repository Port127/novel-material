"""search 脚本共享工具。"""
import re


_TERM_PATTERN = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]+")


def require_database_url(database_url: str | None) -> str:
    """确保 DATABASE_URL 已配置。"""
    if not database_url:
        raise RuntimeError("DATABASE_URL 未配置，请先在 .env 中设置数据库连接串")
    return database_url


def build_like_terms(query: str | None) -> list[str]:
    """从查询语句提取适合 ILIKE 的关键词。

    规则：
    - 保留原始短语，优先匹配整句
    - 再提取连续的中英文/数字片段
    - 去重并保持顺序
    """
    if not query:
        return []

    terms: list[str] = []

    stripped = query.strip()
    if stripped:
        terms.append(stripped)

    for term in _TERM_PATTERN.findall(query):
        normalized = term.strip()
        if normalized:
            terms.append(normalized)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if term not in seen:
            seen.add(term)
            deduped.append(term)

    return deduped
