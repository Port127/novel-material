"""章节数据加载与摘要池构建工具。

这个模块做什么？
- load_chapters_data：加载章节数据列表
- build_summary_pool：构建摘要池（供 LLM 分析时参考）

什么是摘要池？
- LLM 分析小说时，不可能把几千章原文全传过去
- 但可以把每章的摘要（50-100字）传过去
- 摘要池就是这些摘要的合集，让 LLM 了解全书脉络

摘要池怎么处理长篇小说？
- 200 以内：全量使用（直接截断到 Token 上限）
- 200 章以上：分层采样（均匀抽取，覆盖首尾和中间）
"""
import yaml
from pathlib import Path

# 章数超过此值时启用分层采样
_SAMPLE_THRESHOLD = 200
# 每条摘要预估的 Token 数（"第N章《标题》：摘要" ≈ 40 tokens）
_AVG_TOKENS_PER_ENTRY = 40


def load_chapters_data(novel_dir: Path) -> list[dict]:
    """加载章节数据列表。

    加载策略：
    1. 如果 chapters/ 子目录存在且比 chapters.yaml 更新，即时合并返回
       （分析中途断开时，确保下游脚本看到最新数据）
    2. 否则读取 chapters.yaml（分析完成后的合并快照）
    3. 都不存在则返回空列表

    参数：
        novel_dir：小说目录路径

    返回：
        list：章节字典列表，每个字典包含 chapter、title、summary 等字段
    """
    chapters_dir = novel_dir / "chapters"
    chapters_file = novel_dir / "chapters.yaml"

    if chapters_dir.exists():
        individual_files = sorted(chapters_dir.glob("*.yaml"))
        if individual_files:
            # 用最新修改时间判断是否需要重新合并
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
    """构建摘要池文本。

    什么是摘要池？
    - 把所有章节的摘要拼接成一段文本
    - 传给 LLM 作为参考上下文
    - 让 LLM 了解全书内容，而不需要传原文

    短篇小说（≤200 章）：
    - 全量使用，按 Token 上限截断

    长篇小说（>200 章）：
    - 分层采样，均匀抽取覆盖全书
    - 首章和末章必定入选，中间等距分布
    - 避免 LLM 只看前 7-8% 的内容

    参数：
        chapters_data：章节数据列表
        max_tokens：Token 上限
        model：模型名称（用于 Token 计算）

    返回：
        str：摘要池文本，可直接插入 LLM prompt
    """
    from scripts.core.llm_client import truncate_to_tokens

    total = len(chapters_data)

    def _entry(ch: dict) -> str:
        """格式化一条摘要。"""
        return (
            f"第{ch.get('chapter', '?')}章"
            f"《{ch.get('title', '')}》："
            f"{ch.get('summary', '')}"
        )

    if total <= _SAMPLE_THRESHOLD:
        # 短篇：全量拼接后截断
        lines = [_entry(ch) for ch in chapters_data if ch.get("summary")]
        return truncate_to_tokens("\n".join(lines), max_tokens, model=model)

    # 长篇：分层均匀采样
    n_samples = max(50, max_tokens // _AVG_TOKENS_PER_ENTRY)
    n_samples = min(n_samples, total)

    # 首章 + 末章 + 中间等距
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