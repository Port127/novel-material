#!/usr/bin/env python3
"""
build_scene_index.py — 构建场景倒排索引和清单文件

固化核心索引逻辑，避免每次由 agent 动态生成。
读取扁平格式的场景 YAML（遵循 scene.schema.yaml 扁平输出契约）。

用法:
    python scripts/core/build_scene_index.py <material_id>

输出:
    - data/novels/{material_id}/scenes_index.yaml   (倒排索引)
    - data/novels/{material_id}/scenes_manifest.yaml (场景清单)
    - 更新 data/novels/{material_id}/meta.yaml
"""

import argparse
import sys
import yaml
from pathlib import Path
from datetime import datetime
from collections import defaultdict

LIST_FIELDS = [
    'scene_type', 'conflict', 'stakes',
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


def build_index(material_id: str):
    base_dir = Path(f"data/novels/{material_id}")
    scenes_dir = base_dir / "scenes"
    meta_path = base_dir / "meta.yaml"
    index_path = base_dir / "scenes_index.yaml"
    manifest_path = base_dir / "scenes_manifest.yaml"

    if not scenes_dir.exists():
        print(f"ERROR: 场景目录不存在: {scenes_dir}", file=sys.stderr)
        sys.exit(1)

    scene_files = sorted(scenes_dir.glob("ch*.yaml"))
    total_scenes = len(scene_files)
    print(f"场景文件总数: {total_scenes}")

    manifest_scenes = []

    index = defaultdict(lambda: defaultdict(list))

    parse_errors = []

    for i, scene_file in enumerate(scene_files):
        if (i + 1) % 200 == 0:
            print(f"处理进度: {i + 1}/{total_scenes}")

        try:
            with open(scene_file, 'r', encoding='utf-8') as f:
                scene = yaml.safe_load(f)
        except yaml.YAMLError as e:
            parse_errors.append(f"{scene_file.name}: {e}")
            continue

        if scene is None:
            parse_errors.append(f"{scene_file.name}: 文件为空")
            continue

        scene_id = scene.get('id', scene_file.stem)

        summary_raw = scene.get('summary', '')
        summary_short = (summary_raw[:50] + '...') if len(summary_raw) > 50 else summary_raw

        manifest_item = {
            'id': scene_id,
            'chapter': scene.get('chapter', ''),
            'title': scene.get('title', ''),
            'summary': summary_short,
            'scene_type': _as_list(scene.get('scene_type')),
            'conflict': _as_list(scene.get('conflict')),
            'tension': scene.get('tension', 2),
            'pacing': scene.get('pacing', ''),
            'plot_function': _as_list(scene.get('plot_function')),
            'characters': _as_list(scene.get('characters')),
            'emotion': _as_list(scene.get('emotion')),
            'reader_effect': _as_list(scene.get('reader_effect')),
        }
        manifest_scenes.append(manifest_item)

        for field in LIST_FIELDS:
            for v in _as_list(scene.get(field)):
                index[field][v].append(scene_id)

        for field in SCALAR_FIELDS:
            val = scene.get(field)
            if val:
                index[field][val].append(scene_id)

        for c in _as_list(scene.get('characters')):
            index['character'][c].append(scene_id)

        tension_val = scene.get('tension', 2)
        index['tension'][tension_val].append(scene_id)

    index = {k: dict(v) for k, v in index.items()}

    manifest = {
        'material_id': material_id,
        'total_scenes': total_scenes,
        'built_at': datetime.now().isoformat(),
        'scenes': manifest_scenes
    }

    with open(manifest_path, 'w', encoding='utf-8') as f:
        yaml.dump(manifest, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    index_data = {
        'material_id': material_id,
        'total_scenes': total_scenes,
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
        meta['pipeline']['manifest_scenes'] = total_scenes

        with open(meta_path, 'w', encoding='utf-8') as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    char_count = len(index.get('character', {}))
    scene_type_count = len(index.get('scene_type', {}))

    print(f"\n✅ 索引构建完成")
    print(f"场景总数: {total_scenes}")
    print(f"人物索引: {char_count} 个角色")
    print(f"场景类型: {scene_type_count} 种")

    if parse_errors:
        print(f"\n⚠️ 解析失败 {len(parse_errors)} 个文件:")
        for err in parse_errors:
            print(f"  - {err}")


def main():
    parser = argparse.ArgumentParser(description='构建场景倒排索引和清单文件')
    parser.add_argument('material_id', help='素材 ID（如 nm_novel_20260406_dwrn）')
    args = parser.parse_args()

    build_index(args.material_id)


if __name__ == '__main__':
    main()
