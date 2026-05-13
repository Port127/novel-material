"""章节分析：为每章生成摘要、出场人物、功能标签等结构化数据。

工作流程：
1. 读取 chapter_index.yaml（章节索引）和 source.txt（原文）
2. 调用 LLM 分析每章内容，生成：
   - summary：50-100 字摘要
   - characters_appear：出场人物列表
   - chapter_functions：章节功能标签
   - tension_level：紧张程度（1-5）
3. 结果写入 chapters/{章节号}.yaml（每章独立文件）
4. 完成后合并为 chapters.yaml（完整快照）

特性：
- 断点续传：已分析的章节自动跳过，从中断处继续
- 批量处理：可一次分析多章，减少 API 调用次数
- Token 截断：每章内容限制在 LLM_MAX_CHAPTER_TOKENS 内（settings.yaml 默认 5000）
- 滑动窗口（可选）：启用时提供前后章上下文，输出张力变化、情感过渡、情节进度

模块拆分：
- analyze_utils.py：辅助函数和常量
- analyze_single.py：单章分析
- analyze_batch.py：批量分析
- analyze.py：统一入口
"""
import sys
import yaml
import time
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR, update_meta_status, get_settings
from novel_material.infra.llm import load_config, get_last_call_finish_reason, get_call_details
from novel_material.validation.quality import run_quality_check, get_short_summary_chapters, get_missing_chapters
from novel_material.validation.schema import get_schema_error_chapters
from novel_material.validation.pacing_normalize import normalize_pacing
from novel_material.infra.progress import get_pipeline_logger, PipelineRunner
from novel_material.validation.schema import validate_chapter_tags_fields
from novel_material.pipeline.evaluate import load_evaluation

# 导入拆分后的子模块
from novel_material.pipeline.analyze_utils import (
    _fmt_duration,
    _get_batch_size,
    build_sliding_window_context,
    validate_window_fields,
    validate_chapter_analysis,
    _load_existing_chapters,
    _append_chapter,
    _merge_chapters,
)
from novel_material.pipeline.analyze_single import analyze_chapter
from novel_material.pipeline.analyze_batch import analyze_chapters_batch

logger = get_pipeline_logger()


def _reanalyze_chapters(
    material_id: str,
    chapters: list[int],
    provider: str | None = None,
    use_window: bool = False,
    start_ch: int | None = None,
    end_ch: int | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> int:
    """重新分析指定章节（用于 summary 长度自动修复）。

    调用后会自动合并 chapters.yaml，确保断点续传。

    返回成功重新分析的章节数。
    """
    novel_dir = NOVELS_DIR / material_id
    config = load_config(provider)

    # 删除这些章节的分析文件（使用 04d 格式）
    for ch_num in chapters:
        ch_file = novel_dir / "chapters" / f"{ch_num:04d}.yaml"
        if ch_file.exists():
            ch_file.unlink()

    # 读取章节索引和原文
    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")

    # 构建待重新分析的章节列表
    batch_info = [
        ch for ch in chapter_index
        if ch["chapter"] in chapters
    ]

    if not batch_info:
        return 0

    # 滑动窗口模式：加载 evaluation.yaml 和已分析章节
    evaluation = None
    done: dict[int, dict] = {}
    if use_window:
        evaluation = load_evaluation(material_id)
        done = _load_existing_chapters(novel_dir)

    # 逐章重新分析
    success_count = 0
    total_to_reanalyze = len(batch_info)

    for ch_info in batch_info:
        ch_num = ch_info["chapter"]
        chapter_text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])

        try:
            # 构建滑动窗口上下文（如果启用）
            window_context = None
            if use_window:
                window_context = build_sliding_window_context(
                    ch_num, done, lines, chapter_index, evaluation
                )

            # 单章分析
            result = analyze_chapter(
                chapter_text,
                ch_info,
                config,
                progress_ratio=0.0,
                material_id=material_id,
                window_context=window_context,
            )

            result["chapter"] = ch_num
            result["title"] = ch_info["title"]
            result["type"] = ch_info.get("type", "normal")
            result["word_count"] = ch_info.get("word_count", 0)

            # 规范化 pacing
            if "pacing" in result:
                result["pacing"] = normalize_pacing(result["pacing"])

            # 写入章节文件（使用 _append_chapter 保持格式一致）
            _append_chapter(novel_dir, result)
            success_count += 1

            # 进度回调（仅成功时）
            if progress_callback:
                progress_callback(
                    success_count, total_to_reanalyze,
                    f"重分析第 {ch_num} 章 ({success_count}/{total_to_reanalyze})"
                )

            # 更新 done 字典（用于后续章节的窗口上下文）
            if use_window:
                done[ch_num] = result

        except Exception as e:
            logger.warning(f"[{material_id}] 重新分析第 {ch_num} 章失败: {e}")
            # 失败章节也报告进度，让用户知道处理到哪了
            processed_count = success_count + 1  # 失败也算已处理
            if progress_callback:
                progress_callback(
                    processed_count, total_to_reanalyze,
                    f"重分析第 {ch_num} 章 [失败] ({processed_count}/{total_to_reanalyze})"
                )

    # 重分析完成后立即合并 chapters.yaml（确保断点续传）
    _merge_chapters(novel_dir, material_id=material_id)

    return success_count


def chapter_analyze(
    material_id: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
    start_ch: int | None = None,
    end_ch: int | None = None,
    provider: str | None = None,
    use_window: bool = False,
    skip_embedding: bool = False,
) -> bool:
    """对指定小说进行章节分析（支持断点续传和范围指定）。

    流程：
    1. 加载章节索引和原文
    2. 检查已分析的章节（断点续传）
    3. 过滤指定范围内的待处理章节
    4. 批量或逐章分析待处理章节
    5. 合并结果并执行质量检查

    参数：
        material_id：素材 ID（如 nm_novel_20240101_abc1）
        progress_callback：可选进度回调函数 (done: int, total: int, desc: str) -> None
        start_ch：起始章节号（可选，不指定则从第一章开始）
        end_ch：结束章节号（可选，不指定则到最后一章）
        provider：服务商名称（可选，不指定则使用默认配置）
        use_window：是否启用滑动窗口模式（可选，默认 False）
                   启用时会加载 evaluation.yaml 和前章摘要作为上下文
        skip_embedding：是否跳过章节向量化（可选，默认 False）
                       设置为 True 时仅生成章级数据，不生成向量

    返回：
        True 表示成功，False 表示失败
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    config = load_config(provider)

    # 加载小说基本信息
    meta_file = novel_dir / "meta.yaml"
    meta = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "raw")

    with open(novel_dir / "chapter_index.yaml", "r", encoding="utf-8") as f:
        chapter_index = yaml.safe_load(f)

    chapter_count = len(chapter_index)

    # 计算分析范围的起止章节号（用于进度比例计算）
    range_start = start_ch or 1
    range_end = end_ch or chapter_count

    # 输出小说基本信息和范围信息
    range_info = ""
    if start_ch is not None or end_ch is not None:
        range_info = f" | 分析范围: 第 {range_start}-{range_end} 章"
    window_info = " | 滑动窗口模式" if use_window else ""
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}{range_info}{window_info}")

    with open(novel_dir / "source.txt", "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.split("\n")

    # 滑动窗口模式：加载 evaluation.yaml
    evaluation = None
    if use_window:
        evaluation = load_evaluation(material_id)
        if evaluation:
            logger.info(f"[{material_id}] 已加载总体评估：{evaluation.get('novel_type', [])}")
        else:
            logger.warning(f"[{material_id}] 滑动窗口模式但未找到 evaluation.yaml，将无全局上下文")

    # 计算范围内的章节总数
    chapters_in_range = [
        ch for ch in chapter_index
        if (start_ch is None or ch["chapter"] >= start_ch)
        and (end_ch is None or ch["chapter"] <= end_ch)
    ]
    total = len(chapters_in_range)
    rate_limit = config["llm"].get("rate_limit_seconds", 1)
    batch_size = _get_batch_size(config)

    # 滑动窗口模式：禁用批量处理（每章需要前章结果作为上下文）
    if use_window and batch_size > 1:
        logger.info(f"[{material_id}] 滑动窗口模式禁用批量处理，改为逐章分析")
        batch_size = 1

    # 标签校验去重：同一标签只警告一次（避免日志污染）
    warned_tags: set[str] = set()

    completed = 0
    skipped = 0
    total_downgrades = 0
    total_batch_errors = 0

    # 加载已分析的章节（断点续传）
    done = _load_existing_chapters(novel_dir)
    done_in_range = {
        ch_num: data for ch_num, data in done.items()
        if (start_ch is None or ch_num >= start_ch)
        and (end_ch is None or ch_num <= end_ch)
    }
    if done_in_range:
        if progress_callback:
            progress_callback(len(done_in_range), total, f"断点续传：已完成 {len(done_in_range)} 章")
        else:
            next_ch = max(done_in_range.keys()) + 1
            if start_ch and next_ch < start_ch:
                next_ch = start_ch
            logger.info(f"[{material_id}] 断点续传：已完成 {len(done_in_range)} 章，从第 {next_ch} 章继续")

    # 过滤出待处理章节（结合断点续传和范围指定）
    pending = [
        ch for ch in chapter_index
        if ch["chapter"] not in done
        and (start_ch is None or ch["chapter"] >= start_ch)
        and (end_ch is None or ch["chapter"] <= end_ch)
    ]
    skipped = total - len(pending)

    # ETA 估算：记录处理开始时间（跳过已完成章节后的真正起点）
    eta_start_time = time.monotonic() if pending else None

    # PipelineRunner 用于记录运行历史（仅在有待处理章节时创建）
    runner = None

    if not pending:
        if progress_callback:
            progress_callback(total, total, "所有章节已完成")
        else:
            logger.info(f"[{material_id}] 所有 {total} 章已完成，跳过分析")
    else:
        n_batches = (len(pending) + batch_size - 1) // batch_size
        if progress_callback:
            progress_callback(skipped, total, f"待分析 {len(pending)} 章")
        else:
            logger.info(f"[{material_id}] 待分析: {len(pending)} 章，批量大小: {batch_size}，共 {n_batches} 批次")

        # 创建 PipelineRunner 记录运行历史
        runner = PipelineRunner(
            name="章级分析",
            total_stages=n_batches,
            novel_dir=novel_dir,
            material_id=material_id,
            novel_info={"name": title, "chapter_count": chapter_count, "word_count": word_count}
        )

    for batch_idx, batch_start_idx in enumerate(range(0, len(pending), batch_size)):
        batch = pending[batch_start_idx:batch_start_idx + batch_size]
        first_ch = batch[0]["chapter"]
        last_ch = batch[-1]["chapter"]

        # 批次开始时的日志（非回调模式）
        if not progress_callback:
            progress_pct = (batch_idx * batch_size + skipped) / total * 100
            logger.info(
                f"[{material_id}] [批次 {batch_idx + 1}/{n_batches}] 第 {first_ch}-{last_ch} 章 "
                f"| 进度 {skipped + batch_idx * batch_size}/{total} ({progress_pct:.1f}%)"
            )

        batch_start_time = time.monotonic()
        batch_errors = 0
        batch_downgrades = 0
        batch_api_calls = 0
        # 记录 call_details 基准（用于计算增量）
        call_details_base_len = len(get_call_details())

        # 批量分析
        batch_results: dict[int, dict] = {}
        use_batch_mode = batch_size > 1 and len(batch) > 1
        if use_batch_mode:
            try:
                batch_results = analyze_chapters_batch(
                    batch, lines, config, material_id,
                    batch_index=batch_idx,
                    total_batches=n_batches,
                    range_start_ch=range_start,
                    range_end_ch=range_end,
                )
                batch_api_calls += 1
                # 检查章节号是否匹配（不只是数量）
                expected_chapters = set(ch["chapter"] for ch in batch)
                returned_chapters = set(batch_results.keys())
                missing_in_batch = sorted(expected_chapters - returned_chapters)
                if missing_in_batch:
                    logger.warning(f"[{material_id}] 批量返回缺失 {len(missing_in_batch)} 章 {missing_in_batch}，降级为单章补齐")
            except Exception as e:
                logger.warning(f"[{material_id}] 批量分析失败: {e}，降级为逐章模式")
                batch_errors += 1
                batch_api_calls += 1

        # 处理每章结果
        for ch_info in batch:
            ch_num = ch_info["chapter"]
            result = batch_results.get(ch_num)
            window_context = None

            if result is None:
                # 批量失败或缺漏，改用单章分析
                batch_downgrades += 1
                if not progress_callback:
                    logger.info(f"[{material_id}] [降级单章] 第 {ch_num} 章: {ch_info['title']}（批量返回缺失）")
                chapter_text = "\n".join(lines[ch_info["start_line"] - 1:ch_info["end_line"]])
                # 计算单章的进度比例
                ch_progress_ratio = (ch_num - range_start) / max(range_end - range_start + 1, 1)

                # 滑动窗口模式：构建窗口上下文
                if use_window:
                    window_context = build_sliding_window_context(
                        ch_num, done, lines, chapter_index, evaluation
                    )

                try:
                    result = analyze_chapter(
                        chapter_text, ch_info, config,
                        progress_ratio=ch_progress_ratio,
                        material_id=material_id,
                        window_context=window_context,
                    )
                    batch_api_calls += 1
                except Exception as e:
                    # 收集诊断信息
                    from novel_material.pipeline.analyze_utils import _should_use_thinking_mode
                    ch_type = ch_info.get("type", "normal")
                    content_len = len(chapter_text)
                    thinking_budget = _should_use_thinking_mode(ch_progress_ratio, config)
                    thinking_status = "启用" if thinking_budget is not None else "禁用"

                    logger.error(
                        f"[{material_id}] 第 {ch_num} 章分析失败（已重试耗尽）: {e} | "
                        f"诊断: 类型={ch_type} | 内容={content_len}字 | "
                        f"thinking={thinking_status} | 进度={ch_progress_ratio:.2f}"
                    )
                    batch_errors += 1
                    continue

            # 检查结果质量
            errors = validate_chapter_analysis(result, ch_info)
            for err in errors:
                logger.warning(f"[{material_id}] [质量] {err}")
                batch_errors += 1

            # 滑动窗口模式：校验窗口字段
            if use_window and window_context:
                window_errors = validate_window_fields(result, window_context.get("prev_tension_level"))
                for err in window_errors:
                    logger.warning(f"[{material_id}] [窗口] {err}")
                    batch_errors += 1

            # 章节级标签校验（阶段四新增）
            tags_errors = validate_chapter_tags_fields(result)
            for err in tags_errors:
                # 去重：同一标签只警告一次
                if err not in warned_tags:
                    warned_tags.add(err)
                    logger.warning(f"[{material_id}] [标签] {err}")
                batch_errors += 1

            result["chapter"] = ch_num
            result["title"] = ch_info["title"]
            result["type"] = ch_info.get("type", "normal")  # 从索引中获取章节类型
            result["word_count"] = ch_info.get("word_count", 0)  # 从索引中获取正确字数，防御性取值

            # 规范化 pacing（LLM 输出变体 → 标准值）
            if "pacing" in result:
                original = result["pacing"]
                normalized = normalize_pacing(original)
                if normalized != original:
                    logger.info(f"[{material_id}] pacing 规范化: '{original}' → '{normalized}'")
                result["pacing"] = normalized

            # 立即保存（断点续传关键）
            _append_chapter(novel_dir, result)
            completed += 1

            # 更新 done 字典（用于滑动窗口的下一章上下文）
            done[ch_num] = result

            # 进度更新：在每章完成后更新（含 ETA 估算）
            if progress_callback:
                total_done = skipped + completed
                remaining = total - total_done
                desc = f"第 {first_ch}-{last_ch} 章 ({batch_idx + 1}/{n_batches})"

                # ETA 估算：已耗时 × 剩余比例（至少完成 1 后才显示）
                if eta_start_time and total_done > skipped and remaining > 0:
                    elapsed = time.monotonic() - eta_start_time
                    new_done = total_done - skipped  # 本次运行实际完成的章数
                    eta_sec = elapsed * remaining / new_done
                    desc += f" | ETA ~{_fmt_duration(eta_sec)}"

                progress_callback(total_done, total, desc)

        # 批次耗时汇总
        batch_elapsed = time.monotonic() - batch_start_time
        total_downgrades += batch_downgrades
        total_batch_errors += batch_errors

        # 计算批次 tokens 增量
        call_details = get_call_details()
        batch_tokens_in = 0
        batch_tokens_out = 0
        for detail in call_details[call_details_base_len:]:
            batch_tokens_in += detail.get("input_tokens", 0)
            batch_tokens_out += detail.get("output_tokens", 0)

        # 记录批次完成（用于 run_history）
        if runner:
            runner.record_stage_complete(
                stage_name=f"批次{batch_idx + 1}",
                elapsed=batch_elapsed,
                api_calls=batch_api_calls,
                api_errors=batch_errors,
                tokens_in=batch_tokens_in,
                tokens_out=batch_tokens_out
            )

        if not progress_callback:
            finish_reason = get_last_call_finish_reason()
            logger.info(
                f"[{material_id}] [批次 {batch_idx + 1}/{n_batches}] 完成: {batch_elapsed:.1f}s | "
                f"返回 {len(batch_results)}/{len(batch)} 章 | "
                f"降级 {batch_downgrades} 次 | 错误 {batch_errors} 次 | "
                f"finish={finish_reason}"
            )

        # 批次间等待（避免触发速率限制）
        if batch_start_idx + batch_size < len(pending):
            time.sleep(rate_limit)

    # LLM 分析完成，更新进度描述（后续还有质量检查和向量化）
    if progress_callback:
        progress_callback(total, total, f"分析完成: 新增 {completed} 章")
    else:
        logger.info(f"[{material_id}] 章级分析完成: 新分析 {completed} 章，跳过已完成 {skipped} 章，共 {total} 章")
        if total_downgrades > 0:
            total_chapters_attempted = n_batches * batch_size if pending else 1
            downgrade_rate = total_downgrades / total_chapters_attempted * 100
            logger.info(
                f"[{material_id}] 降级统计: {total_downgrades} 次降级（占 {downgrade_rate:.1f}%），"
                f"批次错误 {total_batch_errors} 次"
            )

    # 合并所有章节文件
    if progress_callback:
        progress_callback(total, total, "合并章节数据...")
    _merge_chapters(novel_dir, material_id=material_id)

    # 质量检查（带 summary 长度自动修复）
    max_summary_retries = 3
    final_passed = False

    # 进度转发 wrapper（保持外层进度值，避免进度条跳跃）
    # 内层的 done/total 是重分析章数（如 1/5），外层 total 是全书章数（如 1498）
    def reanalyze_progress_wrapper(inner_done: int, inner_total: int, desc: str):
        if progress_callback:
            # 固定传递外层 (total, total)，只更新描述（内层计数已在 desc 中）
            progress_callback(total, total, desc)

    for retry_idx in range(max_summary_retries):
        if progress_callback:
            progress_callback(total, total, f"质量校验（第 {retry_idx + 1}/{max_summary_retries} 次）...")
        logger.info(f"[{material_id}] 执行章级分析质量校验...")
        if run_quality_check(material_id, start_ch=start_ch, end_ch=end_ch):
            final_passed = True
            break

        # 检查短摘要章节、缺失章节和 schema 错误章节（应用范围过滤）
        short_chapters = get_short_summary_chapters(material_id, start_ch=start_ch, end_ch=end_ch)
        missing_chapters = get_missing_chapters(material_id, start_ch=start_ch, end_ch=end_ch, strict=False)
        schema_error_chapters = get_schema_error_chapters(material_id, start_ch=start_ch, end_ch=end_ch)

        # 合并需要重分析的章节
        chapters_to_reanalyze = sorted(set(short_chapters) | set(missing_chapters) | set(schema_error_chapters))

        if not chapters_to_reanalyze:
            # 不是 summary 问题也不是缺失问题，也不是 schema 问题，无法自动修复
            update_meta_status(material_id, "failed")
            raise ValueError(f"章级分析质量校验未通过：{material_id}")

        # 自动重新分析这些章节
        logger.info(
            f"[{material_id}] 发现 {len(short_chapters)} 章摘要过短 + {len(missing_chapters)} 章缺失 + {len(schema_error_chapters)} 章 schema 错误，"
            f"合并 {len(chapters_to_reanalyze)} 章待重分析（第 {retry_idx + 1}/{max_summary_retries} 次）"
        )
        if progress_callback:
            progress_callback(total, total, f"重分析 {len(chapters_to_reanalyze)} 章...")

        success = _reanalyze_chapters(
            material_id, chapters_to_reanalyze,
            provider=provider,
            use_window=use_window,
            start_ch=start_ch,
            end_ch=end_ch,
            progress_callback=reanalyze_progress_wrapper
        )
        if success < len(chapters_to_reanalyze):
            logger.warning(f"[{material_id}] 重分析部分失败：成功 {success}/{len(chapters_to_reanalyze)} 章")
        # 注：_reanalyze_chapters 内部已自动合并 chapters.yaml

    # 循环未通过时的最终校验
    if not final_passed:
        if progress_callback:
            progress_callback(total, total, "最终校验...")
        if not run_quality_check(material_id, start_ch=start_ch, end_ch=end_ch):
            update_meta_status(material_id, "failed")
            raise ValueError(f"章级分析质量校验未通过（已重试 {max_summary_retries} 次）：{material_id}")

    update_meta_status(material_id, "analyzed")

    # 章节向量化（可选）
    if not skip_embedding:
        from novel_material.storage.embedding import embed_chapters
        # 更新进度描述，让用户知道正在进行向量化（进度条仍显示100%，但描述变化）
        if progress_callback:
            progress_callback(total, total, "正在向量化章节摘要...")
        else:
            logger.info(f"[{material_id}] 生成章节向量...")
        embed_chapters(material_id)
        if progress_callback:
            progress_callback(total, total, f"向量化完成: 共 {total} 章")

    # 保存运行历史
    if runner:
        runner.save_history(status="success")

    return True


def reanalyze_chapters(
    material_id: str,
    chapters: list[int] | None = None,
    provider: str | None = None,
    use_window: bool = False,
    min_success_rate: float = 0.8,
) -> tuple[bool, int, int]:
    """重新分析指定章节（公开接口）。

    支持重分析短摘要章节、缺失章节、schema 错误章节或任意指定章节。
    调用后会自动合并 chapters.yaml。

    参数：
        material_id: 素材 ID
        chapters: 需要重分析的章节列表（None 则自动检测短摘要章节）
        provider: LLM 服务商（应与原始分析一致）
        use_window: 是否使用滑动窗口（应与原始分析一致）
        min_success_rate: 最低成功率阈值（低于此值视为失败）

    返回：
        tuple: (是否成功, 成功章数, 总需重分析章数)
    """
    if chapters is None:
        chapters = get_short_summary_chapters(material_id)

    if not chapters:
        return True, 0, 0

    success_count = _reanalyze_chapters(
        material_id,
        chapters,
        provider=provider,
        use_window=use_window,
    )
    total = len(chapters)
    # 注：_reanalyze_chapters 内部已自动合并 chapters.yaml

    # 判断是否成功（成功率 >= min_success_rate）
    success_rate = success_count / total if total > 0 else 1.0
    success = success_rate >= min_success_rate

    if not success:
        logger.warning(
            f"[{material_id}] 重分析成功率 {success_rate:.1%} 低于阈值 {min_success_rate:.1%}"
        )

    return success, success_count, total


# 向后兼容别名
def repair_short_summaries(
    material_id: str,
    short_chapters: list[int] | None = None,
    provider: str | None = None,
    use_window: bool = False,
    min_success_rate: float = 0.8,
) -> tuple[bool, int, int]:
    """修复 summary 长度不足的章节（向后兼容接口）。

    已更名为 reanalyze_chapters，请使用新函数名。
    """
    return reanalyze_chapters(
        material_id,
        chapters=short_chapters,
        provider=provider,
        use_window=use_window,
        min_success_rate=min_success_rate,
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze.py <material_id>")
        sys.exit(1)

    chapter_analyze(sys.argv[1])