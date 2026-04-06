#!/usr/bin/env python3
"""
batch_split_scenes.py — 批量场景拆分脚本
自动处理全书场景拆分，分批执行
"""

import argparse
import re
import os
from pathlib import Path
import yaml

def extract_chapters(source_path):
    """提取章节索引"""
    text = Path(source_path).read_text(encoding='utf-8')
    lines = text.split('\n')
    
    chapters = []
    chapter_pattern = re.compile(r'^第(\d+)章\s*(.*)$')
    
    for i, line in enumerate(lines, 1):
        match = chapter_pattern.match(line.strip())
        if match:
            num = int(match.group(1))
            title = match.group(2)
            chapters.append({
                'num': num,
                'title': title,
                'line': i
            })
    
    # 计算每章的结束行
    for i in range(len(chapters) - 1):
        chapters[i]['end_line'] = chapters[i + 1]['line'] - 1
    if chapters:
        chapters[-1]['end_line'] = len(lines)
    
    return chapters

def get_batch_ranges(chapters, batch_size=5):
    """生成分批范围"""
    total = len(chapters)
    batches = []
    for i in range(0, total, batch_size):
        batch_chapters = chapters[i:i + batch_size]
        start_ch = batch_chapters[0]['num']
        end_ch = batch_chapters[-1]['num']
        batches.append({
            'range': f"{start_ch}-{end_ch}",
            'chapters': batch_chapters
        })
    return batches

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('material_id', help='素材ID')
    parser.add_argument('--batch-size', type=int, default=5, help='每批章节数')
    parser.add_argument('--dry-run', action='store_true', help='仅显示计划不执行')
    args = parser.parse_args()
    
    source_path = f"data/novels/{args.material_id}/source.txt"
    scenes_dir = f"data/novels/{args.material_id}/scenes"
    
    # 提取章节
    chapters = extract_chapters(source_path)
    print(f"总章节数: {len(chapters)}")
    
    # 生成分批
    batches = get_batch_ranges(chapters, args.batch_size)
    print(f"批次数: {len(batches)}")
    print(f"每批大小: {args.batch_size}章")
    
    if args.dry_run:
        print("\n分批计划:")
        for i, batch in enumerate(batches[:5], 1):
            print(f"  批次 {i}: 第{batch['range']}章")
        if len(batches) > 5:
            print(f"  ... 还有 {len(batches) - 5} 批")
    else:
        # 实际执行时会调用 novel-scenes skill
        print(f"\n准备处理 {len(batches)} 批场景...")
        print(f"使用命令: /novel-scenes {args.material_id} all:{args.batch_size}")

if __name__ == '__main__':
    main()
