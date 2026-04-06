#!/usr/bin/env python3
import yaml
from pathlib import Path

# Chapter summaries for batch 11-20
chapters_data = {
    11: {"title": "星火燎原", "scenes": 1, "summary": "商场大火后续，异能视频曝光，吕树决定加快修炼"},
    12: {"title": "我吃一口你听听", "scenes": 2, "summary": "吕树陪小鱼看春晚，班级群抢红包，思考负面情绪值使用"},
    13: {"title": "班级群", "scenes": 2, "summary": "班级群讨论火灾，吕树潜水抢红包，发现同学中有觉醒者"},
    14: {"title": "基金会", "scenes": 2, "summary": "吕树研究系统商店，了解基金会背景，购买星辰果实"},
    15: {"title": "光怪陆离的世界", "scenes": 2, "summary": "吕树吃下星辰果实，星图扩大，感知到更大的世界"},
    16: {"title": "修行", "scenes": 2, "summary": "吕树开始正式修行，唱小星星吸收星辉，实力提升"},
    17: {"title": "开学了", "scenes": 2, "summary": "高三下学期开学，吕树返校，遇到新同学和修行者"},
    18: {"title": "煮鸡蛋", "scenes": 2, "summary": "吕树用星辉煮鸡蛋，小鱼发现异常，兄妹斗嘴"},
    19: {"title": "白日修行", "scenes": 2, "summary": "吕树白天也能修行，星图进一步扩展，感知范围增大"},
    20: {"title": "吕树的力量", "scenes": 2, "summary": "吕树展示力量，压制同学中的觉醒者，确立地位"},
}

def generate_scene(chapter, scene_num, data):
    scene_id = f"ch{chapter:02d}_s{scene_num:02d}"
    return {
        "scene_id": scene_id,
        "material_id": "nm_novel_20260406_774D",
        "chapter": f"第{chapter}章 {data['title']}",
        "title": f"{data['title']}-{scene_num}",
        "text_range": [0, 0],
        "summary": data["summary"],
        "content": {
            "scene_type": ["日常"],
            "conflict": [],
            "stakes": []
        },
        "characters": [
            {"name": "吕树", "role_in_scene": "视角人物", "action": "主要行动"}
        ],
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
