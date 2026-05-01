"""章节向量化：为每章摘要生成 embedding，写入 chapter_embeddings.yaml。

向量文件与 chapters.yaml 分开存储，避免 YAML 文件因 1024 维浮点数而体积膨胀。
断点续传：已有 embedding 的章节自动跳过。
"""
import sys
import yaml
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from scripts.core.paths import NOVELS_DIR
from scripts.core.embedding import get_embedding, load_embedding_config

# 每批向量化的章节数（OpenAI 支持批量，BGE 逐条）
_BATCH_SIZE = 20
# 批次间等待（秒），避免 API 限流
_RATE_LIMIT = 0.5


def embed_chapters(material_id: str) -> None:
    """对指定小说的所有章节摘要生成 embedding（支持断点续传）。

    读取：chapters.yaml（章节摘要）
    写入：chapter_embeddings.yaml（格式：{chapter_num: [float, ...]}）
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        print("错误: chapters.yaml 不存在，请先运行 chapter_analyze")
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        print("chapters.yaml 为空，跳过向量化")
        return

    embeddings_file = novel_dir / "chapter_embeddings.yaml"

    # 断点续传：加载已有 embedding
    existing: dict[int, list] = {}
    if embeddings_file.exists():
        with open(embeddings_file, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
        print(f"断点续传：已有 {len(existing)} 章向量，跳过")

    # 过滤出需要向量化的章节
    pending = [
        ch for ch in chapters
        if ch.get("summary") and ch.get("chapter") not in existing
    ]

    if not pending:
        print("所有章节已向量化，无需处理")
        return

    print(f"待向量化: {len(pending)} 章（共 {len(chapters)} 章）")

    config = load_embedding_config()
    done = 0

    for i in range(0, len(pending), _BATCH_SIZE):
        batch = pending[i:i + _BATCH_SIZE]
        for ch in batch:
            ch_num = ch["chapter"]
            summary = ch["summary"]
            try:
                vec = get_embedding(summary, config)
                existing[ch_num] = vec
                done += 1
            except Exception as e:
                print(f"  警告: 第{ch_num}章向量化失败: {e}")
                continue

        # 每批写一次磁盘（断点续传）
        with open(embeddings_file, "w", encoding="utf-8") as f:
            yaml.dump(existing, f, allow_unicode=True, default_flow_style=False)

        print(f"  已完成 {done}/{len(pending)} 章")
        if i + _BATCH_SIZE < len(pending):
            time.sleep(_RATE_LIMIT)

    # 校验维度
    sample_vec = next(iter(existing.values()), None)
    if sample_vec:
        print(f"向量化完成: {done} 章，维度 {len(sample_vec)}")
    else:
        print(f"向量化完成: {done} 章")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python embed_chapters.py <material_id>")
        sys.exit(1)

    embed_chapters(sys.argv[1])
