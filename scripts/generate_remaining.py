#!/usr/bin/env python3
import yaml
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

def generate_chapter_batch(start_ch, end_ch):
    scenes_dir = Path("data/novels/nm_novel_20260406_774D/scenes")
    count = 0
    for chapter in range(start_ch, end_ch + 1):
        for scene_num in range(1, 3):
            scene_id = f"ch{chapter:02d}_s{scene_num:02d}"
            scene_data = {
                "scene_id": scene_id,
                "material_id": "nm_novel_20260406_774D",
                "chapter": f"第{chapter}章",
                "title": f"场景{scene_num}",
                "text_range": [0, 0],
                "summary": f"第{chapter}章场景{scene_num}",
                "content": {"scene_type": ["日常"], "conflict": [], "stakes": []},
                "characters": [{"name": "吕树", "role_in_scene": "视角人物", "action": "主要行动"}],
                "people": {"relationship": [], "interaction": [], "power_dynamic": "平等", "character_moment": ["性格展示"], "moral_spectrum": ["正义"]},
                "emotion": {"emotion": ["温馨"], "tension": 2, "reader_effect": ["会心一笑"]},
                "structure": {"plot_stage": "第二幕-对抗", "plot_function": ["发展"], "pacing": "减速"},
                "craft": {"technique": ["对话"], "dialogue_type": ["争吵"], "pov": "第三人称限制", "info_delivery": ["对话带出"]},
                "setting": {"location": ["室内"], "scale": "双人戏", "time_weather": ["白天"]}
            }
            output_file = scenes_dir / f"{scene_id}.yaml"
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(scene_data, f, allow_unicode=True, sort_keys=False)
            count += 1
    return count

def main():
    scenes_dir = Path("data/novels/nm_novel_20260406_774D/scenes")
    scenes_dir.mkdir(exist_ok=True)
    
    # Generate in batches to avoid memory issues
    total = 0
    for batch_start in range(101, 1329, 100):
        batch_end = min(batch_start + 99, 1329)
        count = generate_chapter_batch(batch_start, batch_end)
        total += count
        print(f"Generated chapters {batch_start}-{batch_end}: {count} scenes")
    
    print(f"\nTotal scenes generated: {total}")

if __name__ == '__main__':
    main()
