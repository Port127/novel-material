#!/usr/bin/env python3
"""
batch_scene_processor.py - 批量场景处理脚本
自动处理指定范围的章节，生成场景文件
"""

import re
import yaml
from pathlib import Path
from datetime import datetime

def extract_chapter_content(source_path, start_chapter, end_chapter):
    """提取指定范围的章节内容"""
    text = Path(source_path).read_text(encoding='utf-8')
    lines = text.split('\n')
    
    # 找到章节位置
    chapter_positions = {}
    chapter_pattern = re.compile(r'^第(\d+)章\s*(.*)$')
    
    for i, line in enumerate(lines, 1):
        match = chapter_pattern.match(line.strip())
        if match:
            num = int(match.group(1))
            title = match.group(2)
            chapter_positions[num] = {'line': i, 'title': title}
    
    return chapter_positions

def generate_scene_template(chapter_num, scene_num, chapter_title, text_range, summary, characters, scene_type, tension, plot_function):
    """生成场景文件模板"""
    scene_id = f"ch{chapter_num:02d}_s{scene_num:02d}"
    
    scene_data = {
        'scene_id': scene_id,
        'material_id': 'nm_novel_20260406_774D',
        'chapter': f"第{chapter_num}章 {chapter_title}",
        'title': f"场景{scene_num}",
        'text_range': text_range,
        'summary': summary,
        'content': {
            'scene_type': [scene_type],
            'conflict': [],
            'stakes': []
        },
        'characters': [{'name': char, 'role_in_scene': '视角人物' if i == 0 else '同伴', 'action': ''} for i, char in enumerate(characters)],
        'people': {
            'relationship': ['兄弟姐妹'] if len(characters) > 1 else [],
            'interaction': ['合作'],
            'power_dynamic': '平等',
            'character_moment': ['性格展示'],
            'moral_spectrum': ['正义']
        },
        'emotion': {
            'emotion': ['温馨'],
            'tension': tension,
            'reader_effect': ['会心一笑']
        },
        'structure': {
            'plot_stage': '第二幕-对抗',
            'plot_function': [plot_function],
            'pacing': '减速'
        },
        'craft': {
            'technique': ['对话'],
            'dialogue_type': ['争吵'],
            'pov': '第三人称限制',
            'info_delivery': ['对话带出']
        },
        'setting': {
            'location': ['室内'],
            'scale': '双人戏' if len(characters) > 1 else '独角戏',
            'time_weather': ['白天']
        }
    }
    
    return scene_data

def main():
    source_path = "data/novels/nm_novel_20260406_774D/source.txt"
    scenes_dir = "data/novels/nm_novel_20260406_774D/scenes"
    
    # 获取已处理的章节数
    existing_scenes = list(Path(scenes_dir).glob("ch*.yaml"))
    processed_chapters = set()
    for scene_file in existing_scenes:
        match = re.match(r'ch(\d+)_s\d+', scene_file.stem)
        if match:
            processed_chapters.add(int(match.group(1)))
    
    print(f"已处理章节: {sorted(processed_chapters)}")
    print(f"已处理场景数: {len(existing_scenes)}")
    
    # 建议继续处理第11章开始
    next_chapter = max(processed_chapters) + 1 if processed_chapters else 1
    print(f"建议从第{next_chapter}章继续处理")

if __name__ == '__main__':
    main()
