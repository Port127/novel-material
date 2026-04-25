#!/usr/bin/env python3
"""
build_event_index.py — 构建事件倒排索引和清单文件

固化核心索引逻辑，避免每次由 agent 动态生成。
读取扁平格式的 event YAML（遵循 event-unit.schema.yaml 扁平输出契约）。

用法:
    python scripts/core/build_event_index.py <material_id>

输出:
    - data/novels/{material_id}/events_index.yaml   (倒排索引)
    - data/novels/{material_id}/events_manifest.yaml (事件清单)
    - 更新 data/novels/{material_id}/meta.yaml
"""

import argparse
import sys
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LIST_FIELDS = [
    'event_type', 'conflict', 'stakes',
    'relationship', 'interaction', 'character_moment',
    'emotion', 'reader_effect',
    'plot_function',
    'technique', 'dialogue_type', 'info_delivery',
    'setting', 'time_weather',
]

SCALAR_FIELDS = [
    'power_dynamic', 'moral_spectrum',
    'plot_stage', 'pacing', 'pov', 'scale',
]


def _as_list(val):
    """Normalize a field value to a list for indexing."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def _get_tension(event: dict, default: int = 2) -> int:
    """统一读取事件张力，兼容 tension_peak / tension / legacy nested emotion。"""
    if event.get('tension') is not None:
        return event['tension']
    if event.get('tension_peak') is not None:
        return event['tension_peak']
    emotion = event.get('emotion')
    if isinstance(emotion, dict):
        if emotion.get('tension') is not None:
            return emotion['tension']
        if emotion.get('tension_peak') is not None:
            return emotion['tension_peak']
    return default


def build_index(material_id: str):
    base_dir = Path(f"data/novels/{material_id}")
    events_dir = base_dir / "events"
    meta_path = base_dir / "meta.yaml"
    index_path = base_dir / "events_index.yaml"
    manifest_path = base_dir / "events_manifest.yaml"

    if not events_dir.exists():
        print(f"ERROR: 事件目录不存在: {events_dir}", file=sys.stderr)
        sys.exit(1)

    event_files = sorted(events_dir.glob("ev*.yaml"))
    total_events = len(event_files)
    print(f"事件文件总数: {total_events}")

    manifest_events = []

    index = defaultdict(lambda: defaultdict(list))

    parse_errors = []

    for i, event_file in enumerate(event_files):
        if (i + 1) % 200 == 0:
            print(f"处理进度: {i + 1}/{total_events}")

        try:
            with open(event_file, 'r', encoding='utf-8') as f:
                event = yaml.safe_load(f)
        except yaml.YAMLError as e:
            parse_errors.append(f"{event_file.name}: {e}")
            continue

        if event is None:
            parse_errors.append(f"{event_file.name}: 文件为空")
            continue

        event_id = event.get('id', event_file.stem)

        summary_raw = event.get('summary', '')
        summary_short = (summary_raw[:50] + '...') if len(summary_raw) > 50 else summary_raw

        manifest_item = {
            'id': event_id,
            'chapter': event.get('chapter', ''),
            'title': event.get('title', ''),
            'summary': summary_short,
            'event_type': _as_list(event.get('event_type')),
            'conflict': _as_list(event.get('conflict')),
            'tension': _get_tension(event),
            'pacing': event.get('pacing', ''),
            'plot_function': _as_list(event.get('plot_function')),
            'characters': _as_list(event.get('characters')),
            'emotion': _as_list(event.get('emotion')),
            'reader_effect': _as_list(event.get('reader_effect')),
        }
        manifest_events.append(manifest_item)

        for field in LIST_FIELDS:
            for v in _as_list(event.get(field)):
                index[field][v].append(event_id)

        for field in SCALAR_FIELDS:
            val = event.get(field)
            if val:
                index[field][val].append(event_id)

        for c in _as_list(event.get('characters')):
            index['character'][c].append(event_id)

        tension_val = _get_tension(event)
        index['tension'][tension_val].append(event_id)

    index = {k: dict(v) for k, v in index.items()}

    manifest = {
        'material_id': material_id,
        'total_events': total_events,
        'built_at': datetime.now().isoformat(),
        'events': manifest_events
    }

    with open(manifest_path, 'w', encoding='utf-8') as f:
        yaml.dump(manifest, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    index_data = {
        'material_id': material_id,
        'total_events': total_events,
        'built_at': datetime.now().isoformat(),
        **index
    }

    with open(index_path, 'w', encoding='utf-8') as f:
        yaml.dump(index_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = yaml.safe_load(f)

        if 'pipeline' not in meta:
            meta['pipeline'] = {}
        meta['pipeline']['index_built'] = True
        meta['pipeline']['index_at'] = datetime.now().isoformat()
        meta['pipeline']['manifest_events'] = total_events

        with open(meta_path, 'w', encoding='utf-8') as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    char_count = len(index.get('character', {}))
    event_type_count = len(index.get('event_type', {}))

    print(f"\n✅ 索引构建完成")
    print(f"事件总数: {total_events}")
    print(f"人物索引: {char_count} 个角色")
    print(f"事件类型: {event_type_count} 种")

    if parse_errors:
        print(f"\n⚠️ 解析失败 {len(parse_errors)} 个文件:")
        for err in parse_errors:
            print(f"  - {err}")


def main():
    parser = argparse.ArgumentParser(description='构建事件倒排索引和清单文件')
    parser.add_argument('material_id', help='素材 ID（如 nm_novel_20260406_dwrn）')
    args = parser.parse_args()

    build_index(args.material_id)


if __name__ == '__main__':
    main()
