# 使用指南

> 不用记命令。找到你当前的事件，照着做。

## 目录

1. [入库新素材](#一入库新素材)
2. [导入已分析好的素材](#二导入已分析好的素材)
3. [中断恢复](#三中断恢复)
4. [检索素材](#四检索素材)
5. [管理标签](#五管理标签)
6. [检查质量](#六检查质量)
7. [数据库结构与直接查询](#七数据库结构与直接查询)
8. [重建索引](#八重建索引)
9. [在 novel 项目中使用](#九在-novel-项目中使用)
10. [命令速查](#十命令速查)
11. [脚本一览](#十一脚本一览)
12. [最小记忆集](#十二最小记忆集)

---

## 一、入库新素材

### 短篇（< 300 章）：全自动

```bash
/novel-pipeline full /path/to/novel.txt
```

一键走完 4 个子流水线：入库清洗 → 骨架分析 → 事件拆分+索引 → 精调+统计。确认后自动跑完。

### 长篇（300+ 章）：分段手动调用

事件拆分是最耗时的阶段，大书推荐逐个子流水线执行，每次开新对话：

```bash
# 对话 1：入库+清洗
/pipeline-ingest /path/to/novel.txt

# 对话 2：生成大纲、世界观、人物、标签
/pipeline-analyze nm_novel_20260408_xxxx

# 对话 3、4、5...（事件拆分，每 30 批会提醒你开新对话）
/pipeline-events nm_novel_20260408_xxxx

# 最后一次对话：精调+统计报告
/pipeline-finalize nm_novel_20260408_xxxx
```

### 只想看个骨架，不拆事件

```bash
/novel-pipeline quick /path/to/novel.txt
```

只走入库清洗 + 骨架分析（大纲+世界观+人物+标签）。后续想继续用 `continue`。

### 只想重跑某个阶段

```bash
/novel-pipeline stage nm_novel_20260405_zhbk events
/novel-pipeline stage nm_novel_20260405_zhbk refine
```

会自动备份已有输出为 `.bak`，再重新生成。

---

## 二、导入已分析好的素材

别人（或别的工具）已经把大纲、人物、事件等分析好了，文件按本库 schema 格式组织：

```bash
/material-import /path/to/analyzed_folder
```

**文件夹结构**（全部可选，至少提供一个分析产出物）：

```
analyzed_folder/
├── source.txt              # 原文（可选）
├── outline.yaml            # 大纲
├── worldbuilding.yaml      # 世界观
├── characters.yaml         # 人物体系
├── tags.yaml               # 小说级标签
└── events/                # 事件文件
    ├── ev_main_001.yaml
    └── ...
```

执行过程：
1. 扫描文件夹，检测有哪些文件
2. 校验 YAML 格式 + 标签合法性
3. 根据文件推断 status（有 events → `complete`，有 outline → `outlined`）
4. 预览确认后注册到 `index.yaml`
5. 如有 events 自动建索引

不需要带原文 source.txt，但有的话会一起导入。

---

## 三、中断恢复

### 通用恢复

```bash
/novel-pipeline continue nm_novel_20260405_zhbk
```

自动检测进度，路由到中断的子流水线：
- 先跑质量审计，找出需要重做的批次
- 补处理未覆盖章节
- 从中断点接着来

### 事件拆分中断（最常见）

```bash
/pipeline-events nm_novel_20260405_zhbk
```

直接恢复事件拆分，自动从未处理的章节继续。

---

## 四、检索素材

### 有明确的事件需求

```bash
/material-search-event 恋人在雨中告别
/material-search-event 弱者反杀强者的高潮事件
/material-search-event 催泪但不煽情的技法
```

自动解析为标签组合，查 SQLite 索引返回匹配事件。

### 正在写作，想找灵感

```bash
/material-search-context 我在写一个师徒告别的章节，师父身患重病，想要催泪但克制
```

与 `material-search-event` 的区别：同时返回**事件参考、人物参考、技法参考**三个维度，并解释每个结果的参考价值。

### 想找某本书或某个角色

```bash
/material-search 三体
/material-search 陈汉升
/material-search 冷叙述风格的书
```

自动路由：书名/作者名 → 素材级匹配；角色名 → 人物索引；风格词 → 小说级标签匹配。

### 精确控制查询条件

直接调用底层脚本：

```bash
# 多维标签组合
python scripts/core/search.py event --event-type 对决 --emotion 燃 --relationship 师徒 --limit 10

# 按张力过滤
python scripts/core/search.py event --conflict 人与命运 --reader-effect 催泪 --tension-min 4

# 限定在某本书内搜索
python scripts/core/search.py event --material nm_novel_20260405_zhbk --emotion 悲伤

# 找人物
python scripts/core/search.py character --archetype 导师 --moral-spectrum 灰色

# 全文搜索
python scripts/core/search.py text --query 告别 --limit 20

# 看数据库概况
python scripts/core/search.py stats
```

---

## 五、管理标签

### 事件中出现了标签字典里没有的值

```bash
/tag-add event_type 绑架
/tag-add emotion 矛盾
```

添加到 `data/tags.yaml`，后续事件标注即可使用。

### 两个标签是同一个意思

```bash
/tag-merge 恋人 情侣
```

将所有 `情侣` 替换为 `恋人`，同时更新所有事件文件和索引。

### 想看当前标签字典的全貌

```bash
python -c "import yaml; d=yaml.safe_load(open('data/tags.yaml')); [print(f'{k}: {len(v[\"values\"])}') for k,v in d.items()]"
```

### 标注事件时不确定该打什么标签

打开 `docs/TAG_GUIDE.md`——里面有每个维度的判断依据、易混淆标签对照表、张力校准标准。

---

## 六、检查质量

### 全书事件质量审计

```bash
python scripts/core/quality_audit.py nm_novel_20260405_zhbk --report
```

输出：
- 全书级指标（标签多样性、空字段率、张力分布）
- 质量漂移检测（前期 vs 后期对比）
- 失败批次列表
- `quality_report.yaml` 写入小说文件夹

### 单批质量检查

```bash
python scripts/core/quality_audit.py nm_novel_20260405_zhbk --batch 181-200
```

**注意**：`--batch` 只传本批范围（如 `181-200`），不传累积范围（如 `1-200`）。结果自动写入 `meta.yaml`。

### 事件 YAML 格式校验

```bash
python scripts/core/validate_yaml.py event nm_novel_20260405_zhbk
```

检查：YAML 可解析、必填字段完整、标签值合法、章节名匹配。

---

## 七、数据库结构与直接查询

### 数据库是什么

`data/material.db` 是一个 SQLite 文件，是事件 YAML 的**派生查询加速层**。所有数据的权威来源是 YAML 文件，SQLite 只是为了让检索更快。丢了可以随时用 `python scripts/core/build_db.py` 从 YAML 重建。

### 5 张表

| 表名 | 存什么 | 行数量级 |
|------|--------|---------|
| `novels` | 每本小说一行（ID、书名、作者、状态） | 个位数 |
| `events` | 每个事件一行（章节、标题、摘要、张力值等标量字段） | 数百~数千 |
| `event_tags` | 事件标签的展开表（一个事件的一个标签维度一行） | 数千~数万 |
| `characters` | 人物名册（姓名、角色类型、原型、心理维度） | 数十~数百 |
| `event_characters` | 事件-人物关联（哪个事件出现了谁） | 数千~数万 |

### 直接用 sqlite3 查询

打开数据库：

```bash
sqlite3 data/material.db
```

常用查询：

```sql
-- 看有哪些小说、各多少事件
SELECT n.material_id, n.name, n.total_events FROM novels n;

-- 某本书里张力 >= 4 的高潮事件
SELECT event_id, chapter, title, tension
FROM events
WHERE material_id = 'nm_novel_20260405_zhbk' AND tension >= 4
ORDER BY tension DESC;

-- 哪些事件是「对决」类型
SELECT e.event_id, e.chapter, e.title, e.tension
FROM events e
JOIN event_tags t ON e.event_id = t.event_id
WHERE t.dimension = 'event_type' AND t.value = '对决';

-- 两个标签的 AND 交集（对决 + 燃）
SELECT e.event_id, e.chapter, e.title
FROM events e
WHERE e.event_id IN (SELECT event_id FROM event_tags WHERE dimension='event_type' AND value='对决')
  AND e.event_id IN (SELECT event_id FROM event_tags WHERE dimension='emotion' AND value='燃');

-- 某角色出场的所有事件
SELECT e.event_id, e.chapter, e.title
FROM events e
JOIN event_characters ec ON e.event_id = ec.event_id
WHERE ec.character_name = '陈汉升'
LIMIT 20;

-- 各标签维度的值分布（看哪些标签最常用）
SELECT dimension, value, COUNT(*) as cnt
FROM event_tags
GROUP BY dimension, value
ORDER BY dimension, cnt DESC;

-- 数据库概况
SELECT '小说' as type, COUNT(*) as cnt FROM novels
UNION ALL
SELECT '事件', COUNT(*) FROM events
UNION ALL
SELECT '标签记录', COUNT(*) FROM event_tags
UNION ALL
SELECT '人物', COUNT(*) FROM characters;
```

退出 sqlite3：按 `Ctrl+D` 或输入 `.quit`。

### search.py 参数速查

`search.py` 是 SQLite 的封装，不用写 SQL 也能查。4 个子命令：

**事件检索** `event`：

```bash
python scripts/core/search.py event [过滤条件] [--limit N]
```

| 参数 | 对应维度 | 示例 |
|------|---------|------|
| `--event-type` | event_type | `--event-type 对决` |
| `--conflict` | conflict | `--conflict 生死` |
| `--stakes` | stakes | `--stakes 世界存亡` |
| `--emotion` | emotion | `--emotion 燃` |
| `--reader-effect` | reader_effect | `--reader-effect 催泪` |
| `--relationship` | relationship | `--relationship 师徒` |
| `--interaction` | interaction | `--interaction 告别` |
| `--character-moment` | character_moment | `--character-moment 道德抉择` |
| `--power-dynamic` | power_dynamic | `--power-dynamic 翻转` |
| `--plot-stage` | plot_stage | `--plot-stage 第三幕-高潮` |
| `--plot-function` | plot_function | `--plot-function 转折` |
| `--pacing` | pacing | `--pacing 爆发` |
| `--technique` | technique | `--technique 留白` |
| `--dialogue-type` | dialogue_type | `--dialogue-type 告白` |
| `--pov` | pov | `--pov 第一人称` |
| `--info-delivery` | info_delivery | `--info-delivery 对话带出` |
| `--setting` | setting | `--setting 战场` |
| `--scale` | scale | `--scale 双人戏` |
| `--time-weather` | time_weather | `--time-weather 雨` |
| `--character` | 人物名 | `--character 陈汉升` |
| `--material` | 限定小说 | `--material nm_novel_20260405_zhbk` |
| `--tension-min` | 张力下限 | `--tension-min 4` |
| `--tension-max` | 张力上限 | `--tension-max 2` |

多个条件组合时默认 AND 交集，无结果自动放宽为 OR 并按匹配度排序。

**人物检索** `character`：

```bash
python scripts/core/search.py character [--name X] [--archetype X] [--role X] [--moral-spectrum X] [--material X]
```

**全文搜索** `text`：

```bash
python scripts/core/search.py text --query 告别 [--limit 20]
```

搜索事件的 title 和 summary 中包含关键词的记录。

**数据库概况** `stats`：

```bash
python scripts/core/search.py stats
```

---

## 八、重建索引

### 正常流程（事件拆分后自动执行）

```bash
/build-index nm_novel_20260405_zhbk
```

同时生成 YAML 倒排索引和 SQLite 查询库。

### 手动重建 SQLite

```bash
# 重建单本
python scripts/core/build_db.py --material nm_novel_20260405_zhbk

# 全量重建（所有小说）
python scripts/core/build_db.py

# 增量更新（修改事件后）
python scripts/core/build_db.py --incremental nm_novel_20260405_zhbk
```

SQLite（`data/material.db`）是 YAML 的派生产物，丢了随时重建。

### 手动重建 YAML 索引

```bash
python scripts/core/build_event_index.py nm_novel_20260405_zhbk
```

---

## 九、在 novel 项目中使用

### 写章节时找参考事件

在 `novel` 项目中：

```bash
python ../novel-material/scripts/core/search.py event --emotion 悲伤 --interaction 告别 --technique 留白 --limit 5
```

### 找类似的角色参考

```bash
python ../novel-material/scripts/core/search.py character --archetype 反叛者 --role protagonist
```

### 记录灵感来源

```bash
/inspiration-log nm_novel_20260405_zhbk ch0089_s01 参考了该事件的权力翻转手法
```

### novel 项目怎么配置素材库

`novel` 项目的 `projects/{name}/.novel/meta.yaml` 中：

```yaml
external_refs:
  material_lib: ../novel-material
```

### 素材库不在怎么办

所有依赖素材库的功能都是软依赖，没有素材库照样能写作。有素材库时检索更精准。

---

## 十、命令速查

### 入库 & 导入

| 事件 | 命令 |
|------|------|
| 全自动入库 | `/novel-pipeline full [路径]` |
| 只要骨架 | `/novel-pipeline quick [路径]` |
| 导入已分析好的素材 | `/material-import [文件夹路径]` |
| 恢复中断 | `/novel-pipeline continue [id]` |
| 重跑某阶段 | `/novel-pipeline stage [id] [阶段]` |

### 子流水线（大书推荐）

| 阶段 | 命令 | 耗时 |
|------|------|------|
| ① 入库+清洗 | `/pipeline-ingest [路径]` | ~1分钟 |
| ② 骨架分析 | `/pipeline-analyze [id]` | ~5-10分钟 |
| ③ 事件+索引 | `/pipeline-events [id]` | 可跨对话 |
| ④ 精调+统计 | `/pipeline-finalize [id]` | ~5分钟 |

### 检索

| 事件 | 命令 |
|------|------|
| 事件检索 | `/material-search-event [需求描述]` |
| 写作找灵感 | `/material-search-context [上下文]` |
| 找书/人/风格 | `/material-search [关键词]` |

### 标签

| 事件 | 命令 |
|------|------|
| 加新标签 | `/tag-add [维度] [值]` |
| 合并重复标签 | `/tag-merge [旧值] [新值]` |

---

## 十一、脚本一览

`scripts/` 分两个子目录：

- **`scripts/core/`** — 预制脚本，纳入版本控制
- **`scripts/generated/`** — 运行时自动生成的脚本（如针对特定小说的清洗脚本），已 gitignore

| 脚本 | 功能 | 什么时候用 |
|------|------|-----------|
| `scripts/core/search.py` | SQLite 结构化查询 | 检索事件/人物/全文 |
| `scripts/core/build_db.py` | 构建 SQLite 索引 | 事件拆分后、手动重建 |
| `scripts/core/build_event_index.py` | 构建 YAML 倒排索引 | 事件拆分后（自动调用） |
| `scripts/core/quality_audit.py` | 质量审计 | 每批/全书质量检查 |
| `scripts/core/validate_yaml.py` | YAML 格式校验 | 事件写入后（自动调用） |
| `scripts/core/source_format.py` | 格式清洗 | 入库时（自动调用） |

---

## 十二、最小记忆集

**入库**：
- `/novel-pipeline full [路径]` — 全自动，大书中间会让你开新对话
- `/material-import [文件夹]` — 别人分析好的直接导入

**恢复**：
- `/pipeline-events [id]` — 事件拆分断了接着来（最常用）
- `/novel-pipeline continue [id]` — 不确定断在哪时用这个

**找东西**：
- `/material-search-event [描述]` — 最常用，自然语言描述需求
- `python scripts/core/search.py event --emotion X --technique Y` — 精确控制

**出问题了**：
- `python scripts/core/quality_audit.py [id]` — 质量不对劲
- `python scripts/core/build_db.py` — 索引不对劲
