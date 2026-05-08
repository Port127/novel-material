"""章节数据加载与摘要池构建工具。

核心功能：
- load_chapters_data: 加载章节数据，支持分散文件和合并文件两种格式
- build_summary_pool: 构建摘要池，大书自动采样以控制 token 消耗

数据格式：
- 分散格式：novel_dir/chapters/*.yaml，每个文件包含单章分析结果
- 合并格式：novel_dir/chapters.yaml，包含所有章节的合并列表

调用方：
- worldbuilding.py: 世界观提取，需要全书摘要池作为输入
- outline.py: 大纲生成，需要张力/悬念统计数据
- characters.py: 人物提取，需要章节人物列表用于合并
"""
import yaml
from pathlib import Path

from novel_material.infra.llm import truncate_to_tokens
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()

# 章节数阈值：超过此数量启用分层采样
# 理由：200章以上的小说摘要池超过 8000 tokens，超出 LLM 上下文窗口限制
_SAMPLE_THRESHOLD = 200

# 平均每条摘要的 token 数（实测数据：中文摘要 25-50 tokens）
# 用于估算采样数量，确保摘要池不超限
_AVG_TOKENS_PER_ENTRY = 40


def load_chapters_data(novel_dir: Path) -> list[dict]:
    """加载章节数据列表。

    优先级：
    1. chapters/ 目录下的分散 YAML 文件（章级分析默认输出格式）
    2. chapters.yaml 合并文件（旧格式或手动合并）

    Args:
        novel_dir: 小说素材目录路径（如 NOVELS_DIR/material_id）

    Returns:
        章节数据列表，每项包含 chapter/title/summary/tension_level 等字段。
        加载失败时返回空列表。

    Raises:
        无。错误会被捕获并记录，返回空列表让调用方处理。
    """
    chapters_dir = novel_dir / "chapters"
    chapters_file = novel_dir / "chapters.yaml"

    try:
        # 优先读取分散文件（章级分析的默认输出）
        if chapters_dir.exists():
            individual_files = sorted(chapters_dir.glob("*.yaml"))
            total_files = len(individual_files)
            if individual_files:
                all_chapters = []
                for f in individual_files:
                    try:
                        data = yaml.safe_load(f.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            all_chapters.append(data)
                    except (yaml.YAMLError, IOError) as e:
                        logger.warning(f"[{novel_dir.name}] 跳过异常章节文件 {f.name}: {e}")
                        continue

                if all_chapters:
                    all_chapters.sort(key=lambda x: x.get("chapter", 0))
                    # 加载统计日志
                    failed_count = total_files - len(all_chapters)
                    if failed_count > 0:
                        logger.warning(f"[{novel_dir.name}] 加载完成: {len(all_chapters)}/{total_files} 文件，{failed_count} 个失败")
                    else:
                        logger.debug(f"[{novel_dir.name}] 加载完成: {len(all_chapters)} 个章节文件")
                    return all_chapters

        # 兜底：读取合并文件
        if chapters_file.exists():
            try:
                data = yaml.safe_load(chapters_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    # 验证基本格式：必须是 dict 且有 chapter 和 summary 字段
                    valid_chapters = [
                        ch for ch in data
                        if isinstance(ch, dict) and ch.get("chapter") is not None
                    ]
                    invalid_count = len(data) - len(valid_chapters)
                    if invalid_count > 0:
                        logger.warning(f"[{novel_dir.name}] chapters.yaml 有 {invalid_count} 条无效数据")
                    return valid_chapters
                return []
            except (yaml.YAMLError, IOError) as e:
                logger.warning(f"[{novel_dir.name}] chapters.yaml 加载失败: {e}")

        logger.warning(f"[{novel_dir.name}] 章节数据不存在")
        return []

    except Exception as e:
        logger.error(f"[{novel_dir.name}] 加载章节数据时发生未预期错误: {e}")
        return []


def build_summary_pool(
    chapters_data: list[dict],
    max_tokens: int,
    model: str,
    force_full: bool = False
) -> str:
    """构建摘要池文本。

    策略：
    - 章数 <= 200: 使用全部章节摘要
    - 章数 > 200: 分层均匀采样，覆盖首尾及中间均匀分布
    - force_full=True: 强制全量，不采样（用于序列内上下文）

    采样算法：
    - 固定包含首章（第1章）和尾章（最后一章）
    - 中间章节按步长均匀采样
    - 确保采样数量不超过 max_tokens 限制

    Args:
        chapters_data: 章节数据列表，每项需包含 chapter/title/summary 字段
        max_tokens: 摘要池 token 上限（由调用方配置决定）
        model: LLM 模型名称，用于 token 计算
        force_full: 强制全量模式，跳过采样（默认 False）

    Returns:
        摘要池文本，格式为：
        - 全量模式："第1章《标题》：摘要\n第2章..."
        - 采样模式："（注：原书共 N 章，采样 M 章...）\n第1章..."

    Raises:
        无。truncate_to_tokens 内部有兜底处理（tiktoken 未安装时按字符截断）。
    """
    total = len(chapters_data)

    def _entry(ch: dict) -> str:
        chapter_num = ch.get("chapter", "?")
        title = ch.get("title", "")
        summary = ch.get("summary", "")
        return f"第{chapter_num}章《{title}》：{summary}"

    # 全量模式：小书或强制全量
    if force_full or total <= _SAMPLE_THRESHOLD:
        lines = [_entry(ch) for ch in chapters_data if ch.get("summary")]
        return truncate_to_tokens("\n".join(lines), max_tokens, model)

    # 采样模式：大书分层均匀采样
    # 估算采样数量：基于 token 限制和平均每条 token 数
    n_samples = max_tokens // _AVG_TOKENS_PER_ENTRY
    n_samples = max(50, min(n_samples, total))  # 至少 50 章，最多不超过总数

    # 构建采样索引：首章 + 均匀分布的中间章节 + 尾章
    sampled_indices: list[int] = []

    if n_samples >= 2:
        # 首章
        sampled_indices.append(0)

        # 中间章节：均匀分布
        # 步长计算：(total - 1) / (n_samples - 1) 确保首尾都被包含
        if n_samples > 2:
            step = (total - 1) / (n_samples - 1)
            for i in range(1, n_samples - 1):
                sampled_indices.append(int(i * step))

        # 尾章
        sampled_indices.append(total - 1)
    else:
        # 极端情况：n_samples < 2，只采样首尾
        sampled_indices = [0]
        if total > 1:
            sampled_indices.append(total - 1)

    # 提取采样的章节（过滤无摘要的）
    sampled = [
        chapters_data[i]
        for i in sampled_indices
        if i < total and chapters_data[i].get("summary")
    ]

    header = (
        f"（注：原书共 {total} 章，以下为分层均匀采样 {len(sampled)} 章，"
        f"覆盖全书首尾及中间均匀分布）\n"
    )
    lines = [_entry(ch) for ch in sampled]
    pool_text = header + "\n".join(lines)

    return truncate_to_tokens(pool_text, max_tokens, model)