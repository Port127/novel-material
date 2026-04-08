#!/usr/bin/env python
"""
quality_audit.py — 场景标注质量审计脚本

纯确定性检查，不依赖 LLM。检测标签多样性、空字段率、质量漂移。
可审计全书或单个批次。结果写入 meta.yaml 的 scene_batches 字段。

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
    'scene_type', 'conflict', 'stakes',
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
    'scene_type', 'conflict', 'stakes',
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


def load_scenes(scenes_dir: Path, chapter_range: str = None):
    """Load scene YAML files, optionally filtered by chapter range."""
    scene_files = sorted(scenes_dir.glob("ch*.yaml"))
    if not scene_files:
        return []

    if chapter_range:
        start, end = map(int, chapter_range.split('-'))
        filtered = []
        for sf in scene_files:
            stem = sf.stem
            try:
                ch_num = int(stem.split('_')[0].replace('ch', ''))
                if start <= ch_num <= end:
                    filtered.append(sf)
            except (ValueError, IndexError):
                continue
        scene_files = filtered

    scenes = []
    for sf in scene_files:
        try:
            with open(sf, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                data['_file'] = sf.name
                scenes.append(data)
        except yaml.YAMLError:
            scenes.append({'_file': sf.name, '_parse_error': True})
    return scenes


def compute_batch_quality(scenes: list) -> dict:
    """Compute quality metrics for a batch of scenes."""
    if not scenes:
        return {'status': 'empty', 'scenes_count': 0}

    valid_scenes = [s for s in scenes if not s.get('_parse_error')]
    parse_errors = len(scenes) - len(valid_scenes)

    if not valid_scenes:
        return {
            'status': 'failed',
            'scenes_count': len(scenes),
            'parse_errors': parse_errors,
        }

    n = len(valid_scenes)

    # 1. Tag combination uniqueness
    tag_combos = []
    for s in valid_scenes:
        combo = tuple(sorted(
            _as_list(s.get('scene_type')) +
            _as_list(s.get('emotion')) +
            _as_list(s.get('conflict'))
        ))
        tag_combos.append(combo)
    unique_combos = len(set(tag_combos))
    tag_diversity = round(unique_combos / n, 3) if n > 0 else 0

    # 2. Empty field rate
    empty_count = 0
    total_checks = 0
    for s in valid_scenes:
        for field in TAG_LIST_FIELDS:
            total_checks += 1
            val = s.get(field)
            if val is None or val == [] or val == '':
                empty_count += 1
    empty_field_rate = round(empty_count / total_checks, 3) if total_checks > 0 else 0

    # 3. Tension distribution
    tension_dist = Counter()
    for s in valid_scenes:
        t = s.get('tension', 0)
        tension_dist[int(t)] += 1
    tension_dist = dict(sorted(tension_dist.items()))

    # 4. Average tags per scene
    total_tags = 0
    for s in valid_scenes:
        for field in TAG_LIST_FIELDS:
            total_tags += len(_as_list(s.get(field)))
        for field in TAG_SCALAR_FIELDS:
            if s.get(field):
                total_tags += 1
    avg_tags = round(total_tags / n, 1) if n > 0 else 0

    # 5. Title quality check
    bad_titles = 0
    for s in valid_scenes:
        title = str(s.get('title', ''))
        if not title or title.startswith('场景') or title.replace('场景', '').isdigit():
            bad_titles += 1

    # 6. Summary uniqueness
    summaries = [str(s.get('summary', ''))[:30] for s in valid_scenes]
    unique_summaries = len(set(summaries))
    summary_diversity = round(unique_summaries / n, 3) if n > 0 else 0

    # 7. Tension 5 rate
    t5_count = tension_dist.get(5, 0)
    t5_rate = round(t5_count / n, 3) if n > 0 else 0

    # Scale thresholds based on batch size — tag combos naturally repeat in
    # larger batches because the vocabulary of scene_type+emotion+conflict is
    # finite. Strict thresholds only make sense for small batches.
    if n <= 30:
        diversity_threshold = 0.5
    elif n <= 80:
        diversity_threshold = 0.4
    else:
        diversity_threshold = 0.3

    issues = []
    if tag_diversity < diversity_threshold:
        issues.append(f"标签多样性过低: {tag_diversity} (阈值={diversity_threshold}, 场景数={n})")
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
        'scenes_count': n,
        'parse_errors': parse_errors,
        'quality': {
            'tag_diversity': tag_diversity,
            'empty_field_rate': empty_field_rate,
            'tension_distribution': tension_dist,
            'tension_5_rate': t5_rate,
            'avg_tags_per_scene': avg_tags,
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
    early_tags = avg_metric(early, 'avg_tags_per_scene')
    late_tags = avg_metric(late, 'avg_tags_per_scene')

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
    scenes_dir = base_dir / "scenes"
    meta_path = base_dir / "meta.yaml"

    if not scenes_dir.exists():
        print(f"ERROR: 场景目录不存在: {scenes_dir}", file=sys.stderr)
        sys.exit(1)

    all_scenes = load_scenes(scenes_dir)
    total = len(all_scenes)
    print(f"场景文件总数: {total}")

    if total == 0:
        print("无场景文件，跳过审计")
        return

    # Determine batch boundaries from scene IDs
    ch_nums = []
    for s in all_scenes:
        if s.get('_parse_error'):
            continue
        sid = s.get('id', s.get('_file', ''))
        try:
            ch_num = int(sid.split('_')[0].replace('ch', ''))
            ch_nums.append(ch_num)
        except (ValueError, IndexError):
            continue

    if not ch_nums:
        print("无法从场景ID解析章节号")
        return

    min_ch = min(ch_nums)
    max_ch = max(ch_nums)

    # Read existing batch config from meta
    batch_size = 5
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = yaml.safe_load(f) or {}
        pipeline = meta.get('pipeline', {})
        processed = pipeline.get('scenes_processed', [])
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
        batch_scenes = load_scenes(scenes_dir, batch_range)
        if not batch_scenes:
            continue

        result = compute_batch_quality(batch_scenes)
        result['range'] = batch_range
        result['processed_at'] = datetime.now().isoformat()
        batch_results.append(result)

    # Drift detection
    drift = detect_quality_drift(batch_results)

    # Global stats
    all_valid = [s for s in all_scenes if not s.get('_parse_error')]
    global_quality = compute_batch_quality(all_valid)

    failed_batches = [b['range'] for b in batch_results if b['status'] == 'failed']

    # Print summary
    print(f"\n{'='*50}")
    print(f"📊 质量审计报告 — {material_id}")
    print(f"{'='*50}")
    print(f"场景总数: {total}")
    print(f"批次数: {len(batch_results)}")
    print(f"通过批次: {len(batch_results) - len(failed_batches)}")
    print(f"失败批次: {len(failed_batches)}")
    if failed_batches:
        print(f"  需重做: {', '.join(failed_batches)}")

    q = global_quality.get('quality', {})
    print(f"\n全书指标:")
    print(f"  标签多样性: {q.get('tag_diversity', 'N/A')}")
    print(f"  空字段率: {q.get('empty_field_rate', 'N/A')}")
    print(f"  平均标签数/场景: {q.get('avg_tags_per_scene', 'N/A')}")
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
            'total_scenes': total,
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
        meta['scene_batches'] = batch_results
        meta['quality_drift'] = drift
        with open(meta_path, 'w', encoding='utf-8') as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"📄 批次质量数据已写入 meta.yaml")

    return {
        'total': total,
        'failed_batches': failed_batches,
        'drift': drift,
        'global_quality': global_quality,
    }


def batch_audit(material_id: str, batch_range: str):
    """Audit a single batch and write results to meta.yaml.

    IMPORTANT: batch_range should cover ONLY the new batch (e.g. '181-200'),
    not a cumulative range from chapter 1 (e.g. '1-200'). Cumulative ranges
    inflate scene counts and drag down tag_diversity unfairly.
    """
    base_dir = Path(f"data/novels/{material_id}")
    scenes_dir = base_dir / "scenes"
    meta_path = base_dir / "meta.yaml"

    if not scenes_dir.exists():
        print(f"ERROR: 场景目录不存在: {scenes_dir}", file=sys.stderr)
        sys.exit(1)

    start, end = map(int, batch_range.split('-'))
    if start == 1 and end > 50:
        print(f"⚠️  注意: 范围 {batch_range} 从第1章开始且超过50章，"
              f"可能是累积范围而非单批范围。建议只传入本批新增章节范围。",
              file=sys.stderr)

    scenes = load_scenes(scenes_dir, batch_range)
    if not scenes:
        print(f"批次 {batch_range} 无场景文件")
        return

    result = compute_batch_quality(scenes)
    result['range'] = batch_range
    result['processed_at'] = datetime.now().isoformat()

    q = result.get('quality', {})
    status_icon = '✅' if result['status'] == 'passed' else '❌'

    print(f"{status_icon} 批次 {batch_range}: {result['status']}")
    print(f"  场景数: {result['scenes_count']}")
    print(f"  标签多样性: {q.get('tag_diversity', 'N/A')}")
    print(f"  空字段率: {q.get('empty_field_rate', 'N/A')}")
    print(f"  平均标签数: {q.get('avg_tags_per_scene', 'N/A')}")

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

    batches = meta.get('scene_batches', [])
    found = False
    for i, b in enumerate(batches):
        if b.get('range') == batch_range:
            batches[i] = result
            found = True
            break
    if not found:
        batches.append(result)

    meta['scene_batches'] = batches
    with open(meta_path, 'w', encoding='utf-8') as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"📄 批次结果已写入 meta.yaml")
    return result


def main():
    parser = argparse.ArgumentParser(description='场景标注质量审计')
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
