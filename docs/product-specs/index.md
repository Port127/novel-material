# Product Specs Index

产品规格文档目录。

## Skills 规格

|| Skill | 用途 | 状态 |
||-------|------|------|
|| novel-pipeline | 一键流程编排（full/quick/continue/stage） | 活跃 |
|| material-add | 素材入库 | 活跃 |
|| source-format | 格式清洗（繁简/广告/引号/章节名） | 活跃 |
|| novel-outline | 故事大纲（结构+节奏+伏笔） | 活跃 |
|| novel-characters | 人物体系（名册+关系+弧线） | 活跃 |
|| novel-tags | 小说级多维标签 | 活跃 |
|| novel-scenes | 场景拆分+多维标签（支持 all 模式） | 活跃 |
|| build-index | 构建倒排索引+场景清单 | 活跃 |
|| refine | 精调大纲/人物/标签 | 活跃 |
|| novel-stats | 统计报告+可视化 | 活跃 |
|| material-search | 关键词检索 | 活跃 |
|| material-search-scene | 多维标签检索 | 活跃 |
|| tag-add | 新增标签值 | 活跃 |
|| tag-merge | 合并标签值 | 活跃 |

## 素材类型规格

|| 类型 | 存储路径 | 处理方式 |
||------|----------|----------|
|| novel | `data/novels/` | 大纲 + 人物 + 场景拆分 |
|| image | `data/images/` | 描述生成（未来） |
|| reference | `data/references/` | 直接存储（未来） |

## 标签体系规格

6 层 19 维，详见 `data/tags.yaml`：

|| 层 | 维度 | 用途 |
||----|------|------|
|| A. 内容层 | scene_type, conflict, stakes | 发生了什么 |
|| B. 人物层 | relationship, interaction, power_dynamic, character_moment, moral_spectrum | 谁和谁 |
|| C. 情感层 | emotion, tension, reader_effect | 什么感受 |
|| D. 结构层 | plot_stage, plot_function, pacing | 故事位置 |
|| E. 技法层 | technique, dialogue_type, pov, info_delivery | 怎么写的 |
|| F. 物理层 | setting, scale, time_weather | 什么环境 |

## Related Docs

- [../DESIGN.md](../DESIGN.md)
- [../../AGENTS.md](../../AGENTS.md)