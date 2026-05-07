"""章节数据加载与摘要池构建工具。"""
import yaml
from pathlib import Path

_SAMPLE_THRESHOLD = 200
_AVG_TOKENS_PER_ENTRY = 40


def load_chapters_data(novel_dir: Path) -> list[dict]:
    """加载章节数据列表。"""
    chapters_dir = novel_dir / "chapters"
    chapters_file = novel_dir / "chapters.yaml"

    if chapters_dir.exists():
        individual_files = sorted(chapters_dir.glob("*.yaml"))
        if individual_files:
            newest_file = max(individual_files, key=lambda f: f.stat().st_mtime)
            needs_merge = (
                not chapters_file.exists()
                or newest_file.stat().st_mtime > chapters_file.stat().st_mtime
            )
            if needs_merge:
                all_chapters = []
                for f in individual_files:
                    data = yaml.safe_load(f.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        all_chapters.append(data)
                all_chapters.sort(key=lambda x: x.get("chapter", 0))
                return all_chapters

    if chapters_file.exists():
        return yaml.safe_load(chapters_file.read_text(encoding="utf-8")) or []
    return []


def build_summary_pool(chapters_data: list, max_tokens: int, model: str) -> str:
    """构建摘要池文本。"""
    from novel_material.infra.llm import truncate_to_tokens

    total = len(chapters_data)

    def _entry(ch: dict) -> str:
        return (
            f"第{ch.get('chapter', '?')}章"
            f"《{ch.get('title', '')}》："
            f"{ch.get('summary', '')}"
        )

    if total <= _SAMPLE_THRESHOLD:
        lines = [_entry(ch) for ch in chapters_data if ch.get("summary")]
        return truncate_to_tokens("\n".join(lines), max_tokens, model=model)

    n_samples = max(50, max_tokens // _AVG_TOKENS_PER_ENTRY)
    n_samples = min(n_samples, total)

    sampled_indices: set[int] = {0, total - 1}
    step = total / n_samples
    for i in range(n_samples):
        sampled_indices.add(min(int(i * step), total - 1))

    sampled = [
        chapters_data[i]
        for i in sorted(sampled_indices)
        if chapters_data[i].get("summary")
    ]

    header = (
        f"（注：原书共 {total} 章，以下为分层均匀采样 {len(sampled)} 章，"
        f"覆盖全书首尾及中间均匀分布）\n"
    )
    lines = [_entry(ch) for ch in sampled]
    pool_text = header + "\n".join(lines)
    return truncate_to_tokens(pool_text, max_tokens, model=model)