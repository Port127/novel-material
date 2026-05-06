#!/usr/bin/env python
"""流水线调度：串联入库、分析、同步数据库全流程。"""
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.core.ingest import ingest_file
from scripts.core.chapter_analyze import chapter_analyze
from scripts.core.embed_chapters import embed_chapters
from scripts.core.sync_db import sync_novel
from scripts.core.llm_client import get_api_stats, reset_api_stats
from scripts.analyze.generate_outline import generate_outline
from scripts.analyze.generate_worldbuilding import generate_worldbuilding
from scripts.analyze.generate_characters import generate_characters
from scripts.analyze.generate_tags import generate_tags
from scripts.utils.refine import refine
from scripts.utils.progress_tracker import PipelineRunner, _fmt, get_pipeline_logger
from scripts.core.paths import NOVELS_DIR, update_meta_status

logger = get_pipeline_logger()


def _run_stage(tr, name, fn, is_llm=False):
    """运行一个子阶段，支持 LLM 旋转指示器和异常处理。

    异常时不吞、不 print，直接 raise，让外层统一处理。
    API 计数改由 llm_client 全局计数器提供（get_api_stats），
    不再在 pipeline 层手动 record_api_call。
    """
    sub_t0 = time.monotonic()
    if is_llm:
        tr.start_spinner(f"LLM {name}中")
    try:
        fn()
    finally:
        if is_llm:
            tr.stop_spinner()
    elapsed = time.monotonic() - sub_t0
    logger.info(f"{name} 完成 | 耗时: {_fmt(elapsed)}")
    return elapsed


def _get_novel_dir(material_id: str) -> Path:
    """获取小说目录路径。"""
    return NOVELS_DIR / material_id


def _print_api_summary():
    """打印全局 API 调用统计摘要。"""
    stats = get_api_stats()
    if stats["calls"] > 0:
        logger.info(f"API 总调用: {stats['calls']} 次 | 错误: {stats['errors']} 次 | Tokens: {stats['tokens_total']:,}")


def _has_chapter_embeddings(material_id: str) -> bool:
    """判断素材是否已有章节向量文件。"""
    novel_dir = _get_novel_dir(material_id)
    return any(
        (novel_dir / filename).exists()
        for filename in ("chapter_embeddings.npz", "chapter_embeddings.yaml")
    )


def _bind_runner_novel_dir(runner: PipelineRunner, material_id: str) -> None:
    """在 material_id 确定后，为 runner 绑定小说目录。"""
    runner._novel_dir = _get_novel_dir(material_id)


def pipeline_ingest(file_path):
    """入库流水线：预处理 + 章节切分，生成 source.txt / chapter_index.yaml / meta.yaml。"""
    reset_api_stats()
    runner = PipelineRunner("入库流水线", 1)
    with runner.stage(1, "入库") as tr:
        t0 = time.monotonic()
        material_id = ingest_file(file_path)
        if not material_id:
            logger.error("入库失败")
            return None
        _bind_runner_novel_dir(runner, material_id)
        elapsed = time.monotonic() - t0
        logger.info(f"入库完成 | 耗时: {_fmt(elapsed)} | material_id: {material_id}")
        runner.record_stage_complete("入库", elapsed)
    runner.print_final_summary()
    runner.save_history()
    return material_id


def pipeline_full(file_path):
    """完整流水线：入库 → 章级分析 → 向量化 → 骨架分析 → 精调 → 同步数据库。

    章级分析前置，确保大纲/世界观/人物/标签使用全书摘要池而非原文片段。
    """
    reset_api_stats()
    runner = PipelineRunner("完整流水线", 6)
    wall_start = time.monotonic()
    material_id = None

    logger.info("=" * 60)
    logger.info("开始完整流水线")
    logger.info("=" * 60)

    try:
        # 1. 入库
        with runner.stage(1, "入库") as tr:
            t0 = time.monotonic()
            material_id = ingest_file(file_path)
            if not material_id:
                logger.error("入库失败，终止流水线")
                return
            _bind_runner_novel_dir(runner, material_id)
            elapsed = time.monotonic() - t0
            logger.info(f"入库完成 | 耗时: {_fmt(elapsed)} | material_id: {material_id}")
            runner.record_stage_complete("入库", elapsed)

        # 2. 章级分析
        with runner.stage(2, "章级分析") as tr:
            _run_stage(tr, "分析章节", lambda: chapter_analyze(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("章级分析", tr.elapsed_stage, api["calls"], api["errors"])

        # 3. 章节向量化
        with runner.stage(3, "向量化") as tr:
            _run_stage(tr, "向量化", lambda: embed_chapters(material_id))
            runner.record_stage_complete("向量化", tr.elapsed_stage)

        # 4. 骨架分析（大纲/世界观/人物/标签）
        with runner.stage(4, "骨架分析") as tr:
            for name, fn in [
                ("大纲生成", lambda: generate_outline(material_id)),
                ("世界观提取", lambda: generate_worldbuilding(material_id)),
                ("人物提取", lambda: generate_characters(material_id)),
                ("标签生成", lambda: generate_tags(material_id)),
            ]:
                _run_stage(tr, name, fn, is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("骨架分析", tr.elapsed_stage, api["calls"], api["errors"])

        # 5. 精调
        with runner.stage(5, "精调") as tr:
            _run_stage(tr, "精调", lambda: refine(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("精调", tr.elapsed_stage, api["calls"], api["errors"])

        # 6. 同步数据库
        with runner.stage(6, "同步数据库") as tr:
            _run_stage(tr, "同步", lambda: sync_novel(material_id))
            runner.record_stage_complete("同步数据库", tr.elapsed_stage)

    except Exception:
        logger.exception("流水线执行失败")
        _print_api_summary()
        runner.print_final_summary()
        if material_id:
            try:
                update_meta_status(material_id, "failed")
            except (FileNotFoundError, ValueError):
                pass
            runner.save_history(status="failed")
        raise

    _print_api_summary()
    runner.print_final_summary()
    logger.info(f"完整流水线完成! material_id: {material_id} | 总耗时: {_fmt(time.monotonic() - wall_start)}")
    if material_id:
        try:
            update_meta_status(material_id, "indexed")
        except (FileNotFoundError, ValueError):
            pass
    runner.save_history()


def pipeline_analyze(material_id):
    """分析流水线：章级分析 → 大纲/世界观/人物/标签。"""
    reset_api_stats()
    runner = PipelineRunner("分析流水线", 6, novel_dir=_get_novel_dir(material_id))
    wall_start = time.monotonic()

    logger.info("=" * 60)
    logger.info("开始分析流水线")
    logger.info("=" * 60)

    try:
        with runner.stage(1, "章级分析") as tr:
            _run_stage(tr, "分析章节", lambda: chapter_analyze(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("章级分析", tr.elapsed_stage, api["calls"], api["errors"])

        with runner.stage(2, "大纲生成") as tr:
            _run_stage(tr, "生成大纲", lambda: generate_outline(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("大纲生成", tr.elapsed_stage, api["calls"], api["errors"])

        with runner.stage(3, "世界观提取") as tr:
            _run_stage(tr, "提取世界观", lambda: generate_worldbuilding(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("世界观提取", tr.elapsed_stage, api["calls"], api["errors"])

        with runner.stage(4, "人物提取") as tr:
            _run_stage(tr, "提取人物", lambda: generate_characters(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("人物提取", tr.elapsed_stage, api["calls"], api["errors"])

        with runner.stage(5, "标签生成") as tr:
            _run_stage(tr, "生成标签", lambda: generate_tags(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("标签生成", tr.elapsed_stage, api["calls"], api["errors"])

        with runner.stage(6, "同步数据库") as tr:
            _run_stage(tr, "同步", lambda: sync_novel(material_id))
            runner.record_stage_complete("同步数据库", tr.elapsed_stage)

    except Exception:
        _print_api_summary()
        runner.print_final_summary()
        try:
            update_meta_status(material_id, "failed")
        except (FileNotFoundError, ValueError):
            pass
        runner.save_history(status="failed")
        raise

    _print_api_summary()
    runner.print_final_summary()
    logger.info(f"分析流水线完成! 总耗时: {_fmt(time.monotonic() - wall_start)}")
    try:
        update_meta_status(material_id, "analyzed")
    except (FileNotFoundError, ValueError):
        pass
    runner.save_history()


def pipeline_finalize(material_id):
    """收尾流水线：精调 + 同步数据库。"""
    reset_api_stats()
    runner = PipelineRunner("收尾流水线", 2, novel_dir=_get_novel_dir(material_id))
    wall_start = time.monotonic()

    logger.info("=" * 60)
    logger.info("开始收尾流水线")
    logger.info("=" * 60)

    try:
        with runner.stage(1, "精调") as tr:
            _run_stage(tr, "精调", lambda: refine(material_id), is_llm=True)
            api = get_api_stats()
            runner.record_stage_complete("精调", tr.elapsed_stage, api["calls"], api["errors"])

        with runner.stage(2, "同步数据库") as tr:
            _run_stage(tr, "同步", lambda: sync_novel(material_id))
            runner.record_stage_complete("同步数据库", tr.elapsed_stage)

    except Exception:
        _print_api_summary()
        runner.print_final_summary()
        try:
            update_meta_status(material_id, "failed")
        except (FileNotFoundError, ValueError):
            pass
        runner.save_history(status="failed")
        raise

    _print_api_summary()
    runner.print_final_summary()
    logger.info(f"收尾流水线完成! 总耗时: {_fmt(time.monotonic() - wall_start)}")
    try:
        update_meta_status(
            material_id,
            "indexed" if _has_chapter_embeddings(material_id) else "analyzed",
        )
    except (FileNotFoundError, ValueError):
        pass
    runner.save_history()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python pipeline.py ingest  <文件路径>       # 入库（预处理+章节切分）")
        print("  python pipeline.py full    <文件路径>       # 完整流水线")
        print("  python pipeline.py analyze <material_id>   # 分析流水线")
        print("  python pipeline.py finalize <material_id>  # 收尾流水线")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "ingest":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py ingest <文件路径>")
            sys.exit(1)
        pipeline_ingest(sys.argv[2])
    elif mode == "full":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py full <文件路径>")
            sys.exit(1)
        pipeline_full(sys.argv[2])
    elif mode == "analyze":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py analyze <material_id>")
            sys.exit(1)
        pipeline_analyze(sys.argv[2])
    elif mode == "finalize":
        if len(sys.argv) < 3:
            print("用法: python pipeline.py finalize <material_id>")
            sys.exit(1)
        pipeline_finalize(sys.argv[2])
    else:
        print(f"未知模式: {mode}")
        print("可用模式: ingest, full, analyze, finalize")
        sys.exit(1)
