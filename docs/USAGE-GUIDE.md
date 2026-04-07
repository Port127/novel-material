# 使用指南：按场景找命令

> 不用记命令。找到你当前的场景，照着做。

---

## 一、我有一本新小说要入库

### 有一个 txt 文件，想全自动处理

```bash
/novel-pipeline full /path/to/novel.txt
```

一键走完 10 个阶段：入库 → 格式清洗 → 大纲 → 世界观 → 人物 → 标签 → 场景拆分 → 索引 → 精调 → 统计报告。全程有预览确认，确认后自动跑完。

**超长小说（1000+ 章）提示**：场景拆分阶段会自动分批。每 30 批（约 150 章）后会提醒你考虑开新会话 `continue` 恢复，避免质量下降。

### 只想先看个骨架，不拆场景

```bash
/novel-pipeline quick /path/to/novel.txt
```

只做前 5 步：入库 → 格式清洗 → 大纲 → 世界观 → 人物。后续想继续用 `continue`。

### 之前跑到一半断了

```bash
/novel-pipeline continue nm_novel_20260405_zhbk
```

自动检测进度：
- 先跑质量审计，找出需要重做的批次
- 补处理未覆盖章节
- 从中断的阶段接着来

### 只想重跑某个阶段

```bash
/novel-pipeline stage nm_novel_20260405_zhbk scenes
/novel-pipeline stage nm_novel_20260405_zhbk refine
```

会自动备份已有输出为 `.bak`，再重新生成。

---

## 二、我想找参考素材

### 有明确的场景需求

```bash
/material-search-scene 恋人在雨中告别
/material-search-scene 弱者反杀强者的高潮场景
/material-search-scene 催泪但不煽情的技法
```

自动解析为标签组合，查 SQLite 索引返回匹配场景。

### 正在写作，想找灵感

```bash
/material-search-context 我在写一个师徒告别的章节，师父身患重病，想要催泪但克制
```

与 `material-search-scene` 的区别：这个会**同时返回场景参考、人物参考、技法参考**三个维度，并解释每个结果的参考价值。

### 想找某本书或某个角色

```bash
/material-search 三体
/material-search 陈汉升
/material-search 冷叙述风格的书
```

自动路由：书名/作者名 → 素材级匹配；角色名 → 人物索引；风格词 → 小说级标签匹配。

### 想精确控制查询条件

直接调用底层脚本，参数随意组合：

```bash
# 多维标签组合
python scripts/search.py scene --scene-type 对决 --emotion 燃 --relationship 师徒 --limit 10

# 按张力过滤
python scripts/search.py scene --conflict 人与命运 --reader-effect 催泪 --tension-min 4

# 限定在某本书内搜索
python scripts/search.py scene --material nm_novel_20260405_zhbk --emotion 悲伤

# 找人物
python scripts/search.py character --archetype 导师 --moral-spectrum 灰色

# 全文搜索
python scripts/search.py text --query 告别 --limit 20

# 看数据库概况
python scripts/search.py stats
```

---

## 三、我想管理标签

### 场景中出现了标签字典里没有的值

```bash
/tag-add scene_type 绑架
/tag-add emotion 矛盾
```

添加到 `data/tags.yaml`，后续场景标注即可使用。

### 两个标签是同一个意思

```bash
/tag-merge 恋人 情侣
```

将所有 `情侣` 替换为 `恋人`，同时更新所有场景文件和索引。

### 想看当前标签字典的全貌

```bash
python -c "import yaml; d=yaml.safe_load(open('data/tags.yaml')); [print(f'{k}: {len(v[\"values\"])}') for k,v in d.items()]"
```

### 标注场景时不确定该打什么标签

打开 `docs/TAG_GUIDE.md`——里面有每个维度的判断依据、易混淆标签对照表、张力校准标准。

---

## 四、我想检查质量

### 全书场景质量审计

```bash
python scripts/quality_audit.py nm_novel_20260405_zhbk --report
```

输出：
- 全书级指标（标签多样性、空字段率、张力分布）
- 质量漂移检测（前期 vs 后期对比）
- 失败批次列表
- `quality_report.yaml` 写入小说文件夹

### 单批质量检查

```bash
python scripts/quality_audit.py nm_novel_20260405_zhbk --batch 6-10
```

结果自动写入 `meta.yaml` 的 `scene_batches` 字段。

### 场景 YAML 格式校验

```bash
python scripts/validate_yaml.py scene nm_novel_20260405_zhbk
```

检查：YAML 可解析、必填字段完整、标签值合法、章节名匹配。

---

## 五、我想重建索引

### 正常流程（场景拆分后自动执行）

```bash
/build-index nm_novel_20260405_zhbk
```

同时生成 YAML 倒排索引和 SQLite 查询库。

### 手动重建 SQLite

```bash
# 重建单本
python scripts/build_db.py --material nm_novel_20260405_zhbk

# 全量重建（所有小说）
python scripts/build_db.py

# 增量更新（修改场景后）
python scripts/build_db.py --incremental nm_novel_20260405_zhbk
```

SQLite（`data/material.db`）是 YAML 的派生产物，丢了随时重建。

### 手动重建 YAML 索引

```bash
python scripts/build_scene_index.py nm_novel_20260405_zhbk
```

---

## 六、我在 novel 项目里想用素材

### 写章节时找参考场景

在 `novel` 项目中：

```bash
python ../novel-material/scripts/search.py scene --emotion 悲伤 --interaction 告别 --technique 留白 --limit 5
```

### 找类似的角色参考

```bash
python ../novel-material/scripts/search.py character --archetype 反叛者 --role protagonist
```

### 记录灵感来源

```bash
/inspiration-log nm_novel_20260405_zhbk ch0089_s01 参考了该场景的权力翻转手法
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

## 七、Pipeline 快速参考

| 我想做什么 | 用哪个 |
|-----------|-------|
| 一本书全自动处理 | `/novel-pipeline full [路径]` |
| 只要大纲和人物 | `/novel-pipeline quick [路径]` |
| 接着上次继续 | `/novel-pipeline continue [id]` |
| 重跑某个阶段 | `/novel-pipeline stage [id] [阶段]` |
| 找参考场景 | `/material-search-scene [需求]` |
| 写作时找灵感 | `/material-search-context [上下文]` |
| 找书/找人/找风格 | `/material-search [关键词]` |
| 加新标签 | `/tag-add [维度] [值]` |
| 合并重复标签 | `/tag-merge [旧值] [新值]` |

---

## 八、脚本一览

| 脚本 | 功能 | 什么时候用 |
|------|------|-----------|
| `scripts/search.py` | SQLite 结构化查询 | 检索场景/人物/全文 |
| `scripts/build_db.py` | 构建 SQLite 索引 | 场景拆分后、手动重建 |
| `scripts/build_scene_index.py` | 构建 YAML 倒排索引 | 场景拆分后（自动调用） |
| `scripts/quality_audit.py` | 质量审计 | 每批/全书质量检查 |
| `scripts/validate_yaml.py` | YAML 格式校验 | 场景写入后（自动调用） |
| `scripts/source_format.py` | 格式清洗 | 入库时（自动调用） |

---

## 九、最小记忆集

**入库一本书：**
- `/novel-pipeline full [路径]` — 全自动，确认后不用管

**找东西：**
- `/material-search-scene [描述]` — 最常用，自然语言描述需求
- `python scripts/search.py scene --emotion X --technique Y` — 精确控制

**出问题了：**
- `python scripts/quality_audit.py [id]` — 质量不对劲时跑一下
- `python scripts/build_db.py` — 索引不对劲时重建
- `/novel-pipeline continue [id]` — 中断了接着来
