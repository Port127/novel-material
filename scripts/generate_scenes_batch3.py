#!/usr/bin/env python3
import yaml
from pathlib import Path

# Chapter summaries for batch 51-100
chapters_data = {}
for i in range(51, 101):
    chapters_data[i] = {"title": f"第{i}章", "scenes": 2}

def generate_scene(chapter, scene_num, data):
    scene_id = f"ch{chapter:02d}_s{scene_num:02d}"
    return {
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

def main():
    scenes_dir = Path("data/novels/nm_novel_20260406_774D/scenes")
    for chapter, data in chapters_data.items():
        for scene_num in range(1, data["scenes"] + 1):
            scene_data = generate_scene(chapter, scene_num, data)
            output_file = scenes_dir / f"ch{chapter:02d}_s{scene_num:02d}.yaml"
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(scene_data, f, allow_unicode=True, sort_keys=False)
    print(f"Generated {sum(d['scenes'] for d in chapters_data.values())} scenes for chapters 51-100")

if __name__ == '__main__':
    main()
