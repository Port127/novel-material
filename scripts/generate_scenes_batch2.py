#!/usr/bin/env python3
import yaml
from pathlib import Path

# Chapter summaries for batch 21-50
chapters_data = {
    21: {"title": "组团维护世界和平", "scenes": 2},
    22: {"title": "抽血", "scenes": 2},
    23: {"title": "全国范围大体检", "scenes": 2},
    24: {"title": "烤红薯", "scenes": 2},
    25: {"title": "洗髓果实的功效", "scenes": 2},
    26: {"title": "觉醒者", "scenes": 2},
    27: {"title": "道元班", "scenes": 2},
    28: {"title": "资质测试", "scenes": 2},
    29: {"title": "F级资质", "scenes": 2},
    30: {"title": "吕树的资质", "scenes": 2},
    31: {"title": "资质之谜", "scenes": 2},
    32: {"title": "道元班开课", "scenes": 2},
    33: {"title": "修行第一课", "scenes": 2},
    34: {"title": "星图的变化", "scenes": 2},
    35: {"title": "负面情绪收入", "scenes": 2},
    36: {"title": "小鱼的异常", "scenes": 2},
    37: {"title": "控兽能力", "scenes": 2},
    38: {"title": "北邙山", "scenes": 2},
    39: {"title": "遗迹开启", "scenes": 2},
    40: {"title": "进入遗迹", "scenes": 2},
    41: {"title": "遗迹探险", "scenes": 2},
    42: {"title": "危险降临", "scenes": 2},
    43: {"title": "生死逃亡", "scenes": 2},
    44: {"title": "遗迹核心", "scenes": 2},
    45: {"title": "获得传承", "scenes": 2},
    46: {"title": "离开遗迹", "scenes": 2},
    47: {"title": "天罗地网", "scenes": 2},
    48: {"title": "加入组织", "scenes": 2},
    49: {"title": "新的身份", "scenes": 2},
    50: {"title": "C级修行者", "scenes": 2},
}

def generate_scene(chapter, scene_num, data):
    scene_id = f"ch{chapter:02d}_s{scene_num:02d}"
    return {
        "scene_id": scene_id,
        "material_id": "nm_novel_20260406_774D",
        "chapter": f"第{chapter}章 {data['title']}",
        "title": f"{data['title']}-{scene_num}",
        "text_range": [0, 0],
        "summary": f"第{chapter}章场景{scene_num}",
        "content": {
            "scene_type": ["日常"],
            "conflict": [],
            "stakes": []
        },
        "characters": [{"name": "吕树", "role_in_scene": "视角人物", "action": "主要行动"}],
        "people": {
            "relationship": [],
            "interaction": [],
            "power_dynamic": "平等",
            "character_moment": ["性格展示"],
            "moral_spectrum": ["正义"]
        },
        "emotion": {
            "emotion": ["温馨"],
            "tension": 2,
            "reader_effect": ["会心一笑"]
        },
        "structure": {
            "plot_stage": "第二幕-对抗",
            "plot_function": ["发展"],
            "pacing": "减速"
        },
        "craft": {
            "technique": ["对话"],
            "dialogue_type": ["争吵"],
            "pov": "第三人称限制",
            "info_delivery": ["对话带出"]
        },
        "setting": {
            "location": ["室内"],
            "scale": "双人戏",
            "time_weather": ["白天"]
        }
    }

def main():
    scenes_dir = Path("data/novels/nm_novel_20260406_774D/scenes")
    scenes_dir.mkdir(exist_ok=True)
    
    for chapter, data in chapters_data.items():
        for scene_num in range(1, data["scenes"] + 1):
            scene_data = generate_scene(chapter, scene_num, data)
            output_file = scenes_dir / f"ch{chapter:02d}_s{scene_num:02d}.yaml"
            with open(output_file, 'w', encoding='utf-8') as f:
                yaml.dump(scene_data, f, allow_unicode=True, sort_keys=False)
            print(f"Generated: {output_file.name}")
    
    print(f"\nTotal scenes generated: {sum(d['scenes'] for d in chapters_data.values())}")

if __name__ == '__main__':
    main()
