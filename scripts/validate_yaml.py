#!/usr/bin/env python3
"""
validate_yaml.py — 通用 YAML 校验脚本

校验场景文件（必填字段 + 标签值合法性 + 章节名匹配）和其他产出文件。

用法:
    python scripts/validate_yaml.py scene <material_id>          # 校验全部场景
    python scripts/validate_yaml.py scene <material_id> ch0001   # 校验单个/匹配前缀
    python scripts/validate_yaml.py meta <material_id>           # 校验 meta.yaml
    python scripts/validate_yaml.py all <material_id>            # 校验全部产出

输出:
    校验报告（stdout），失败文件列表，exit code 0=全部通过, 1=有失败
"""

import argparse
import sys
import yaml
from pathlib import Path
from collections import defaultdict


SCENE_TAG_FIELDS = {
    'scene_type': list, 'conflict': list, 'stakes': list,
    'relationship': list, 'interaction': list, 'power_dynamic': str,
    'character_moment': list, 'moral_spectrum': str,
    'emotion': list, 'reader_effect': list,
    'plot_stage': str, 'plot_function': list, 'pacing': str,
    'technique': list, 'dialogue_type': list, 'pov': str, 'info_delivery': list,
    'setting': list, 'scale': str, 'time_weather': list,
}

NESTED_MAP = {
    'content': ['scene_type', 'conflict', 'stakes'],
    'people': ['relationship', 'interaction', 'power_dynamic', 'character_moment', 'moral_spectrum'],
    'emotion': ['emotion', 'reader_effect'],
    'structure': ['plot_stage', 'plot_function', 'pacing'],
    'craft': ['technique', 'dialogue_type', 'pov', 'info_delivery'],
    'setting': ['scale', 'time_weather'],
}

NESTED_REMAP = {
    'location': 'setting',
}

META_REQUIRED_FIELDS = ['material_id', 'type', 'name', 'source', 'status']


def load_tags_dict():
    """Load tags.yaml and return {dimension: set(values)}."""
    tags_path = Path("data/tags.yaml")
    if not tags_path.exists():
        print("WARNING: data/tags.yaml 不存在，跳过标签合法性检查", file=sys.stderr)
        return None
    with open(tags_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    result = {}
    for dim, info in raw.items():
        if isinstance(info, dict) and 'values' in info:
            result[dim] = set(str(v) for v in info['values'])
    return result


def load_chapter_index(base_dir: Path):
    """Load chapter_index.yaml titles as a set."""
    ci_path = base_dir / "chapter_index.yaml"
    if not ci_path.exists():
        return None
    with open(ci_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    if not raw:
        return None
    titles = set()
    chapters = raw if isinstance(raw, list) else raw.get('chapters', [])
    for ch in chapters:
        if isinstance(ch, dict) and 'title' in ch:
            titles.add(ch['title'])
    return titles if titles else None


def _flatten_scene(raw: dict) -> dict:
    """Normalize nested scene format to flat format for uniform validation.

    Handles both flat format (scene.schema.yaml Flat Output Contract)
    and legacy nested format (content/people/emotion/structure/craft/setting groups).
    """
    flat = dict(raw)

    if 'scene_id' in flat and 'id' not in flat:
        flat['id'] = flat.pop('scene_id')

    for group_key, fields in NESTED_MAP.items():
        if group_key in flat and isinstance(flat[group_key], dict):
            group = flat.pop(group_key)
            for f in fields:
                if f in group and f not in flat:
                    flat[f] = group[f]
            for old_name, new_name in NESTED_REMAP.items():
                if old_name in group and new_name not in flat:
                    flat[new_name] = group[old_name]

    if 'tension' not in flat:
        emo = raw.get('emotion')
        if isinstance(emo, dict) and 'tension' in emo:
            flat['tension'] = emo['tension']

    if 'characters' in flat and isinstance(flat['characters'], list):
        first = flat['characters'][0] if flat['characters'] else None
        if isinstance(first, dict) and 'name' in first:
            flat['characters'] = [c['name'] for c in flat['characters'] if isinstance(c, dict)]

    if 'moral_spectrum' in flat and isinstance(flat['moral_spectrum'], list):
        flat['moral_spectrum'] = flat['moral_spectrum'][0] if flat['moral_spectrum'] else ''

    return flat


def validate_scene(scene_path: Path, tags_dict, chapter_titles):
    """Validate a single scene YAML file. Returns list of error strings."""
    errors = []

    try:
        with open(scene_path, 'r', encoding='utf-8') as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML 解析失败: {e}"]

    if raw is None:
        return ["文件为空"]

    if not isinstance(raw, dict):
        return [f"顶层不是字典，实际类型: {type(raw).__name__}"]

    scene = _flatten_scene(raw)

    core_fields = {'id': str, 'chapter': str, 'title': str, 'summary': str}
    for field, expected_type in core_fields.items():
        if field not in scene:
            errors.append(f"缺少必填字段: {field}")
        elif not isinstance(scene[field], expected_type) and scene[field] is not None:
            errors.append(f"字段 {field} 应为 {expected_type.__name__}，实际: {type(scene[field]).__name__}")

    for field, expected_type in SCENE_TAG_FIELDS.items():
        if field not in scene:
            errors.append(f"缺少标签字段: {field}")
        elif expected_type == list and not isinstance(scene[field], list):
            if scene[field] is not None:
                errors.append(f"字段 {field} 应为列表，实际: {type(scene[field]).__name__}")
        elif expected_type == str and not isinstance(scene[field], str):
            if scene[field] is not None:
                errors.append(f"字段 {field} 应为字符串，实际: {type(scene[field]).__name__}")

    if 'tension' not in scene:
        errors.append(f"缺少必填字段: tension")
    elif isinstance(scene.get('tension'), (int, float)):
        if not (1 <= scene['tension'] <= 5):
            errors.append(f"tension 值越界: {scene['tension']}（应为 1-5）")

    if 'title' in scene and isinstance(scene['title'], str):
        title = scene['title'].strip()
        if title.startswith('场景') and title[2:].isdigit():
            errors.append(f"title 无语义: '{title}'（禁止纯编号）")

    if tags_dict:
        for field in SCENE_TAG_FIELDS:
            if field not in scene:
                continue
            val = scene[field]
            if field not in tags_dict:
                continue
            allowed = tags_dict[field]
            if isinstance(val, list):
                for v in val:
                    if str(v) not in allowed:
                        errors.append(f"标签越界: {field}='{v}'（不在 tags.yaml 中）")
            elif val is not None:
                if str(val) not in allowed:
                    errors.append(f"标签越界: {field}='{val}'（不在 tags.yaml 中）")

    if chapter_titles and 'chapter' in scene:
        ch = scene['chapter']
        if isinstance(ch, str) and ch not in chapter_titles:
            errors.append(f"章节名不匹配: '{ch}'（不在 chapter_index.yaml 中）")

    return errors


def validate_yaml_parseable(path: Path):
    """Check if a YAML file is parseable. Returns list of error strings."""
    if not path.exists():
        return [f"文件不存在: {path}"]
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data is None:
            return ["文件为空"]
        return []
    except yaml.YAMLError as e:
        return [f"YAML 解析失败: {e}"]


def validate_meta(base_dir: Path):
    """Validate meta.yaml required fields."""
    meta_path = base_dir / "meta.yaml"
    errors = validate_yaml_parseable(meta_path)
    if errors:
        return errors

    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = yaml.safe_load(f)

    for field in META_REQUIRED_FIELDS:
        if field not in meta:
            errors.append(f"缺少必填字段: {field}")

    status = meta.get('status', '')
    valid_statuses = {'raw', 'outlined', 'tagged', 'complete', 'refined'}
    if status and status not in valid_statuses:
        errors.append(f"status 值无效: '{status}'（应为 {valid_statuses}）")

    return errors


def cmd_scene(material_id: str, pattern: str = None):
    """Validate scene files."""
    base_dir = Path(f"data/novels/{material_id}")
    scenes_dir = base_dir / "scenes"

    if not scenes_dir.exists():
        print(f"ERROR: 场景目录不存在: {scenes_dir}", file=sys.stderr)
        return 1

    tags_dict = load_tags_dict()
    chapter_titles = load_chapter_index(base_dir)

    if pattern:
        scene_files = sorted(scenes_dir.glob(f"{pattern}*.yaml"))
    else:
        scene_files = sorted(scenes_dir.glob("ch*.yaml"))

    if not scene_files:
        print(f"WARNING: 未找到匹配的场景文件")
        return 0

    total = len(scene_files)
    failed_count = 0
    error_details = []

    for sf in scene_files:
        errs = validate_scene(sf, tags_dict, chapter_titles)
        if errs:
            failed_count += 1
            error_details.append((sf.name, errs))

    passed = total - failed_count

    print(f"📊 场景校验报告: {material_id}")
    print(f"   总文件数: {total}")
    print(f"   通过: {passed}")
    print(f"   失败: {failed_count}")

    if tags_dict is None:
        print(f"   ⚠️ tags.yaml 缺失，标签合法性未校验")
    if chapter_titles is None:
        print(f"   ⚠️ chapter_index.yaml 缺失，章节名未校验")

    if error_details:
        print(f"\n❌ 失败文件详情:")
        for name, errs in error_details[:50]:
            print(f"\n  {name}:")
            for e in errs:
                print(f"    - {e}")
        if len(error_details) > 50:
            print(f"\n  ... 及其他 {len(error_details) - 50} 个文件")

    if failed_count == 0:
        print(f"\n✅ 全部通过")

    return 1 if failed_count > 0 else 0


def cmd_meta(material_id: str):
    """Validate meta.yaml."""
    base_dir = Path(f"data/novels/{material_id}")
    errs = validate_meta(base_dir)
    if errs:
        print(f"❌ meta.yaml 校验失败:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"✅ meta.yaml 校验通过")
    return 0


def cmd_all(material_id: str):
    """Validate all output files."""
    base_dir = Path(f"data/novels/{material_id}")
    if not base_dir.exists():
        print(f"ERROR: 目录不存在: {base_dir}", file=sys.stderr)
        return 1

    exit_code = 0
    results = []

    yaml_files = [
        ('meta.yaml', True),
        ('outline.yaml', False),
        ('worldbuilding.yaml', False),
        ('characters.yaml', False),
        ('tags.yaml', False),
        ('scenes_index.yaml', False),
        ('scenes_manifest.yaml', False),
        ('stats.yaml', False),
    ]

    print(f"📊 全量校验报告: {material_id}\n")

    for filename, required in yaml_files:
        filepath = base_dir / filename
        if not filepath.exists():
            if required:
                print(f"  ❌ {filename}: 不存在（必需）")
                exit_code = 1
            else:
                print(f"  ⏭️  {filename}: 不存在（跳过）")
            continue

        if filename == 'meta.yaml':
            errs = validate_meta(base_dir)
        else:
            errs = validate_yaml_parseable(filepath)

        if errs:
            print(f"  ❌ {filename}: {'; '.join(errs)}")
            exit_code = 1
        else:
            print(f"  ✅ {filename}")

    scenes_dir = base_dir / "scenes"
    if scenes_dir.exists():
        print()
        scene_exit = cmd_scene(material_id)
        if scene_exit != 0:
            exit_code = 1
    else:
        print(f"\n  ⏭️  scenes/: 不存在（跳过）")

    return exit_code


def main():
    parser = argparse.ArgumentParser(description='通用 YAML 校验脚本')
    subparsers = parser.add_subparsers(dest='command', required=True)

    scene_parser = subparsers.add_parser('scene', help='校验场景文件')
    scene_parser.add_argument('material_id', help='素材 ID')
    scene_parser.add_argument('pattern', nargs='?', help='场景 ID 前缀（如 ch0001）')

    meta_parser = subparsers.add_parser('meta', help='校验 meta.yaml')
    meta_parser.add_argument('material_id', help='素材 ID')

    all_parser = subparsers.add_parser('all', help='校验全部产出')
    all_parser.add_argument('material_id', help='素材 ID')

    args = parser.parse_args()

    if args.command == 'scene':
        sys.exit(cmd_scene(args.material_id, args.pattern))
    elif args.command == 'meta':
        sys.exit(cmd_meta(args.material_id))
    elif args.command == 'all':
        sys.exit(cmd_all(args.material_id))


if __name__ == '__main__':
    main()
