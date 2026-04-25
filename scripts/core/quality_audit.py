#!/usr/bin/env python
"""
quality_audit.py — 事件标注质量审计脚本

纯确定性检查，不依赖 LLM。检测标签多样性、空字段率、质量漂移。
可审计全书或单个批次。结果写入 meta.yaml 的 event_batches 字段。

用法:
    python scripts/core/quality_audit.py <material_id>                    # 全书审计
    python scripts/core/quality_audit.py <material_id> --batch 1-5        # 单批审计（写入 meta）
    python scripts/core/quality_audit.py <material_id> --report            # 输出 quality_report.yaml
"""

import argparse
import sys
import yaml
import json
from pathlib import Path
from datetime import datetime
from collections import Counter, defaultdict

TAG_LIST_FIELDS = [
    'event_type', 'conflict', 'stakes',
    'relationship', 'interaction', 'character_moment',
    'emotion', 'reader_effect',
    'plot_function',
    'technique', 'dialogue_type', 'info_delivery',
    'setting', 'time_weather',
]

TAG_SCALAR_FIELDS = [
    'power_dynamic', 'moral_spectrum',
    'plot_stage', 'pacing', 'pov', 'scale',
]

ALL_TAG_FIELDS = TAG_LIST_FIELDS + TAG_SCALAR_FIELDS

REQUIRED_FIELDS = [
    'id', 'chapter', 'title', 'summary',
    'event_type', 'conflict', 'stakes',
    'characters', 'relationship', 'interaction',
    'power_dynamic', 'character_moment', 'moral_spectrum',
    'emotion', 'tension', 'reader_effect',
    'plot_stage', 'plot_function', 'pacing',
    'technique', 'dialogue_type', 'pov', 'info_delivery',
    'setting', 'scale', 'time_weather',
]


def _as_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]


def _get_tension(event: dict, default: int = 0) -> int:
    """统一读取张力，兼容 legacy tension_peak。"""
    tension = event.get('tension')
    if tension is None:
        tension = event.get('tension_peak', default)
    try:
        return int(tension)
    except (ValueError, TypeError):
        return default


def load_events(events_dir: Path, chapter_range: str = None):
    """Load event YAML files, optionally filtered by chapter range."""
    event_files = sorted(events_dir.glob("ev*.yaml"))
    if not event_files:
        return []

    if chapter_range:
        start, end = map(int, chapter_range.split('-'))
        filtered = []
        for ef in event_files:
            stem = ef.stem
            try:
                # Extract chapter number from event ID (e.g., ev_main_001 -> check if related to chapter)
                # For now, use a simpler approach: check if the file name contains chapter info
                # or read the file to get chapter field
                with open(ef, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                if data and 'chapters' in data:
                    ch_nums = data.get('chapters', [])
                    if isinstance(ch_nums, list) and any(start <= int(ch) <= end for ch in ch_nums if isinstance(ch, (int, str)) and str(ch).isdigit()):
                        filtered.append(ef)
            except (ValueError, IndexError, yaml.YAMLError):
                continue
        event_files = filtered

    events = []
    for ef in event_files:
        try:
            with open(ef, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                data['_file'] = ef.name
                events.append(data)
        except yaml.YAMLError:
            events.append({'_file': ef.name, '_parse_error': True})
    return events


def compute_batch_quality(events: list) -> dict:
    """Compute quality metrics for a batch of events."""
    if not events:
        return {'status': 'empty', 'events_count': 0}

    valid_events = [e for e in events if not e.get('_parse_error')]
    parse_errors = len(events) - len(valid_events)

    if not valid_events:
        return {
            'status': 'failed',
            'events_count': len(events),
            'parse_errors': parse_errors,
        }

    n = len(valid_events)

    # 1. Tag combination uniqueness
    tag_combos = []
    for e in valid_events:
        combo = tuple(sorted(
            _as_list(e.get('event_type')) +
            _as_list(e.get('emotion')) +
            _as_list(e.get('conflict'))
        ))
        tag_combos.append(combo)
    unique_combos = len(set(tag_combos))
    tag_diversity = round(unique_combos / n, 3) if n > 0 else 0

    # 2. Empty field rate
    empty_count = 0
    total_checks = 0
    for e in valid_events:
        for field in TAG_LIST_FIELDS:
            total_checks += 1
            val = e.get(field)
            if val is None or val == [] or val == '':
                empty_count += 1
    empty_field_rate = round(empty_count / total_checks, 3) if total_checks > 0 else 0

    # 3. Tension distribution
    tension_dist = Counter()
    for e in valid_events:
        tension_dist[_get_tension(e, 0)] += 1
    tension_dist = dict(sorted(tension_dist.items()))

    # 4. Average tags per event
    total_tags = 0
    for e in valid_events:
        for field in TAG_LIST_FIELDS:
            total_tags += len(_as_list(e.get(field)))
        for field in TAG_SCALAR_FIELDS:
            if e.get(field):
                total_tags += 1
    avg_tags = round(total_tags / n, 1) if n > 0 else 0

    # 5. Title quality check
    bad_titles = 0
    for e in valid_events:
        title = str(e.get('title', ''))
        if not title or title.startswith('事件') or title.replace('事件', '').isdigit():
            bad_titles += 1

    # 6. Summary uniqueness
    summaries = [str(e.get('summary', ''))[:30] for e in valid_events]
    unique_summaries = len(set(summaries))
    summary_diversity = round(unique_summaries / n, 3) if n > 0 else 0

    # 7. Tension 5 rate
    t5_count = tension_dist.get(5, 0)
    t5_rate = round(t5_count / n, 3) if n > 0 else 0

    # Scale thresholds based on batch size
    if n <= 30:
        diversity_threshold = 0.5
    elif n <= 80:
        diversity_threshold = 0.4
    else:
        diversity_threshold = 0.3

    issues = []
    if tag_diversity < diversity_threshold:
        issues.append(f"标签多样性过低: {tag_diversity} (阈值={diversity_threshold}, 事件数={n})")
    if empty_field_rate > 0.3:
        issues.append(f"空字段率过高: {empty_field_rate}")
    if bad_titles > 0:
        issues.append(f"无语义标题: {bad_titles}个")
    if summary_diversity < 0.8:
        issues.append(f"摘要雷同: diversity={summary_diversity}")
    if parse_errors > 0:
        issues.append(f"YAML解析失败: {parse_errors}个")

    status = 'failed' if issues else 'passed'

    return {
        'status': status,
        'events_count': n,
        'parse_errors': parse_errors,
        'quality': {
            'tag_diversity': tag_diversity,
            'empty_field_rate': empty_field_rate,
            'tension_distribution': tension_dist,
            'tension_5_rate': t5_rate,
            'avg_tags_per_event': avg_tags,
            'summary_diversity': summary_diversity,
            'bad_titles': bad_titles,
        },
        'issues': issues if issues else None,
    }


def detect_quality_drift(batches: list) -> dict:
    """Compare early vs late batches to detect quality degradation."""
    if len(batches) < 6:
        return {'drift_detected': False, 'reason': '批次不足，无法检测漂移'}

    passed = [b for b in batches if b.get('quality')]
    if len(passed) < 6:
        return {'drift_detected': False, 'reason': '有效批次不足'}

    third = len(passed) // 3
    early = passed[:third]
    late = passed[-third:]

    def avg_metric(batch_list, key):
        vals = [b['quality'].get(key, 0) for b in batch_list]
        return sum(vals) / len(vals) if vals else 0

    early_div = avg_metric(early, 'tag_diversity')
    late_div = avg_metric(late, 'tag_diversity')
    early_empty = avg_metric(early, 'empty_field_rate')
    late_empty = avg_metric(late, 'empty_field_rate')
    early_tags = avg_metric(early, 'avg_tags_per_event')
    late_tags = avg_metric(late, 'avg_tags_per_event')

    warnings = []
    if late_div < early_div * 0.7:
        warnings.append(
            f"标签多样性下降: 前期={early_div:.3f} → 后期={late_div:.3f}"
        )
    if late_empty > early_empty * 1.5 and late_empty > 0.1:
        warnings.append(
            f"空字段率上升: 前期={early_empty:.3f} → 后期={late_empty:.3f}"
        )
    if late_tags < early_tags * 0.7:
        warnings.append(
            f"平均标签数下降: 前期={early_tags:.1f} → 后期={late_tags:.1f}"
        )

    return {
        'drift_detected': bool(warnings),
        'warnings': warnings if warnings else None,
        'metrics': {
            'early_tag_diversity': round(early_div, 3),
            'late_tag_diversity': round(late_div, 3),
            'early_empty_rate': round(early_empty, 3),
            'late_empty_rate': round(late_empty, 3),
            'early_avg_tags': round(early_tags, 1),
            'late_avg_tags': round(late_tags, 1),
        }
    }


def full_audit(material_id: str, write_report: bool = False):
    """Run full-book quality audit."""
    base_dir = Path(f"data/novels/{material_id}")
    events_dir = base_dir / "events"
    meta_path = base_dir / "meta.yaml"

    if not events_dir.exists():
        print(f"ERROR: 事件目录不存在: {events_dir}", file=sys.stderr)
        sys.exit(1)

    all_events = load_events(events_dir)
    total = len(all_events)
    print(f"事件文件总数: {total}")

    if total == 0:
        print("无事件文件，跳过审计")
        return

    # Determine batch boundaries from event IDs
    ch_nums = []
    for e in all_events:
        if e.get('_parse_error'):
            continue
        chapters = e.get('chapters', [])
        if isinstance(chapters, list):
            for ch in chapters:
                try:
                    ch_num = int(ch)
                    ch_nums.append(ch_num)
                except (ValueError, TypeError):
                    continue

    if not ch_nums:
        print("无法从事件数据解析章节号")
        return

    min_ch = min(ch_nums)
    max_ch = max(ch_nums)

    # Read existing batch config from meta
    batch_size = 5
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = yaml.safe_load(f) or {}
        pipeline = meta.get('pipeline', {})
        processed = pipeline.get('events_processed', [])
        if processed and isinstance(processed[0], str) and '-' in processed[0]:
            try:
                first_range = processed[0]
                s, e = map(int, first_range.split('-'))
                batch_size = e - s + 1
            except ValueError:
                pass

    # Build batches
    batch_results = []
    for batch_start in range(min_ch, max_ch + 1, batch_size):
        batch_end = min(batch_start + batch_size - 1, max_ch)
        batch_range = f"{batch_start}-{batch_end}"
        batch_events = load_events(events_dir, batch_range)
        if not batch_events:
            continue

        result = compute_batch_quality(batch_events)
        result['range'] = batch_range
        result['processed_at'] = datetime.now().isoformat()
        batch_results.append(result)

    # Drift detection
    drift = detect_quality_drift(batch_results)

    # Global stats
    all_valid = [e for e in all_events if not e.get('_parse_error')]
    global_quality = compute_batch_quality(all_valid)

    failed_batches = [b['range'] for b in batch_results if b['status'] == 'failed']

    _exit_blocked = False

    # ── Gate 0: Determine total_chapters from chapter_index.yaml ──
    chapter_index_path = base_dir / "chapter_index.yaml"
    if chapter_index_path.exists():
        with open(chapter_index_path, 'r', encoding='utf-8') as f:
            ci = yaml.safe_load(f) or {}
        total_chapters = ci.get('total', max_ch)
    else:
        total_chapters = max_ch

    # ── Gate 1: Event density check ──
    density_result = check_event_density(all_valid, total_chapters)
    print(f"\n事件密度:")
    print(f"  主线事件: {density_result['main_event_count']}/{total_chapters} 章")
    print(f"  总事件: {density_result['total_event_count']}/{total_chapters} 章")
    print(f"  密度: {density_result['density']:.3f}")
    if density_result['density'] < 0.25:
        print(f"\n🚫 密度严重不足 (< 0.25)，禁止进入下一阶段")
        if density_result.get('issues'):
            for issue in density_result['issues']:
                print(f"  - {issue}")
        print("  请补切事件后重新审计")
        _exit_blocked = True
    elif density_result['density'] < 0.4:
        print(f"\n⚠️  密度偏低 (0.25 ≤ 密度 < 0.4)，建议补切事件")
        if density_result.get('issues'):
            for issue in density_result['issues']:
                print(f"  - {issue}")

    # ── Gate 2: Chapter coverage check ──
    coverage_result = check_chapter_coverage(all_valid, total_chapters)
    print(f"\n章节覆盖:")
    print(f"  已覆盖: {coverage_result['coverage_rate']:.1%} ({len(coverage_result['covered_chapters'])}/{total_chapters})")
    print(f"  最大连续缺口: {coverage_result['max_consecutive_gap']} 章")
    if coverage_result['missing_chapters']:
        missing_str = ', '.join(str(c) for c in coverage_result['missing_chapters'][:20])
        suffix = '...' if len(coverage_result['missing_chapters']) > 20 else ''
        print(f"  未覆盖章节: {missing_str}{suffix}")
    if coverage_result['status'] == 'fail':
        print(f"\n🚫 连续未覆盖章节超过 3 章，禁止进入下一阶段")
        print("  请补切事件后重新审计")
        _exit_blocked = True

    # Print summary
    print(f"\n{'='*50}")
    print(f"📊 质量审计报告 — {material_id}")
    print(f"{'='*50}")
    print(f"事件总数: {total}")
    print(f"批次数: {len(batch_results)}")
    print(f"通过批次: {len(batch_results) - len(failed_batches)}")
    print(f"失败批次: {len(failed_batches)}")
    if failed_batches:
        print(f"  需重做: {', '.join(failed_batches)}")

    q = global_quality.get('quality', {})
    print(f"\n全书指标:")
    print(f"  标签多样性: {q.get('tag_diversity', 'N/A')}")
    print(f"  空字段率: {q.get('empty_field_rate', 'N/A')}")
    print(f"  平均标签数/事件: {q.get('avg_tags_per_event', 'N/A')}")
    print(f"  tension=5 占比: {q.get('tension_5_rate', 'N/A')}")
    print(f"  张力分布: {q.get('tension_distribution', {})}")

    if drift.get('drift_detected'):
        print(f"\n⚠️  质量漂移检测:")
        for w in drift.get('warnings', []):
            print(f"  - {w}")
    else:
        print(f"\n✅ 未检测到质量漂移")

    # Write report
    if write_report:
        report = {
            'material_id': material_id,
            'audited_at': datetime.now().isoformat(),
            'total_events': total,
            'global_quality': global_quality.get('quality'),
            'drift': drift,
            'failed_batches': failed_batches,
            'batches': batch_results,
        }
        report_path = base_dir / "quality_report.yaml"
        with open(report_path, 'w', encoding='utf-8') as f:
            yaml.dump(report, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"\n📄 报告已写入: {report_path}")

    # Update meta.yaml with batch data
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = yaml.safe_load(f) or {}
        meta['event_batches'] = batch_results
        meta['quality_drift'] = drift
        meta['event_density'] = density_result
        meta['chapter_coverage'] = coverage_result
        with open(meta_path, 'w', encoding='utf-8') as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"📄 批次质量数据已写入 meta.yaml")

    # Deferred exit: allow report/meta to be written before blocking
    if locals().get('_exit_blocked'):
        sys.exit(1)

    return {
        'total': total,
        'failed_batches': failed_batches,
        'drift': drift,
        'global_quality': global_quality,
        'event_density': density_result,
        'chapter_coverage': coverage_result,
    }


def batch_audit(material_id: str, batch_range: str):
    """Audit a single batch and write results to meta.yaml.

    IMPORTANT: batch_range should cover ONLY the new batch (e.g. '181-200'),
    not a cumulative range from chapter 1 (e.g. '1-200'). Cumulative ranges
    inflate event counts and drag down tag_diversity unfairly.
    """
    base_dir = Path(f"data/novels/{material_id}")
    events_dir = base_dir / "events"
    meta_path = base_dir / "meta.yaml"

    if not events_dir.exists():
        print(f"ERROR: 事件目录不存在: {events_dir}", file=sys.stderr)
        sys.exit(1)

    start, end = map(int, batch_range.split('-'))
    if start == 1 and end > 50:
        print(f"⚠️  注意: 范围 {batch_range} 从第1章开始且超过50章，"
              f"可能是累积范围而非单批范围。建议只传入本批新增章节范围。",
              file=sys.stderr)

    events = load_events(events_dir, batch_range)
    if not events:
        print(f"批次 {batch_range} 无事件文件")
        return

    result = compute_batch_quality(events)
    result['range'] = batch_range
    result['processed_at'] = datetime.now().isoformat()

    q = result.get('quality', {})
    status_icon = '✅' if result['status'] == 'passed' else '❌'

    print(f"{status_icon} 批次 {batch_range}: {result['status']}")
    print(f"  事件数: {result['events_count']}")
    print(f"  标签多样性: {q.get('tag_diversity', 'N/A')}")
    print(f"  空字段率: {q.get('empty_field_rate', 'N/A')}")
    print(f"  平均标签数: {q.get('avg_tags_per_event', 'N/A')}")

    if result.get('issues'):
        print(f"  问题:")
        for issue in result['issues']:
            print(f"    - {issue}")

    # Upsert into meta.yaml
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = yaml.safe_load(f) or {}
    else:
        meta = {}

    batches = meta.get('event_batches', [])
    found = False
    for i, b in enumerate(batches):
        if b.get('range') == batch_range:
            batches[i] = result
            found = True
            break
    if not found:
        batches.append(result)

    meta['event_batches'] = batches
    with open(meta_path, 'w', encoding='utf-8') as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"📄 批次结果已写入 meta.yaml")
    return result


def check_chapter_coverage(events: list, total_chapters: int) -> dict:
    """检查事件对章节的覆盖情况。"""
    covered = set()
    for e in events:
        if isinstance(e, dict):
            for ch in e.get('chapters', []):
                try:
                    covered.add(int(ch))
                except (ValueError, TypeError):
                    continue

    missing = sorted(set(range(1, total_chapters + 1)) - covered)

    # 计算最大连续缺口
    max_gap = 0
    current_gap = 0
    for i in range(1, total_chapters + 1):
        if i not in covered:
            current_gap += 1
            max_gap = max(max_gap, current_gap)
        else:
            current_gap = 0

    return {
        'covered_chapters': sorted(covered),
        'coverage_rate': round(len(covered) / total_chapters, 3) if total_chapters > 0 else 0,
        'missing_chapters': missing,
        'max_consecutive_gap': max_gap,
        'status': 'pass' if max_gap <= 3 else 'fail',
    }


def check_event_density(events: list, total_chapters: int) -> dict:
    """检查事件密度是否合理。"""
    main_events = [e for e in events if e.get('thread') == 'main']
    density = len(main_events) / total_chapters if total_chapters > 0 else 0

    issues = []
    if density < 0.4:
        issues.append(
            f"事件密度过低: {density:.2f} (每章 {len(main_events)} 个主线事件 / {total_chapters} 章)"
        )

    return {
        'main_event_count': len(main_events),
        'total_event_count': len(events),
        'total_chapters': total_chapters,
        'density': round(density, 3),
        'status': 'pass' if density >= 0.4 else 'fail',
        'issues': issues if issues else None,
    }


def main():
    parser = argparse.ArgumentParser(description='事件标注质量审计')
    parser.add_argument('material_id', help='素材 ID')
    parser.add_argument('--batch', help='审计单批（如 1-5, 6-10）', default=None)
    parser.add_argument('--report', action='store_true', help='输出 quality_report.yaml')

    args = parser.parse_args()

    if args.batch:
        batch_audit(args.material_id, args.batch)
    else:
        full_audit(args.material_id, write_report=args.report)


if __name__ == '__main__':
    main()
