# 后端 API 文档

## 概述

后端基于 **FastAPI** 构建，提供 RESTful API 供前端调用。数据源为项目 `data/` 目录下的 SQLite 数据库（`material.db`）和各小说的 YAML 文件。

- 默认地址: `http://127.0.0.1:8000`
- API 前缀: `/api`
- 自动文档: `http://127.0.0.1:8000/docs` (Swagger UI)

## 快速启动

```bash
cd backend
pip install -r requirements.txt
python main.py
```

服务启动后监听 `0.0.0.0:8000`，开发模式下自动热重载。

## 依赖

| 包 | 用途 |
|---|------|
| fastapi | Web 框架 |
| uvicorn | ASGI 服务器 |
| pyyaml | 读写 YAML 文件 |
| python-multipart | 文件上传 (multipart/form-data) |
| httpx | LLM API 代理的 HTTP 客户端 |

## 项目结构

```
backend/
├── main.py                  # 应用入口，注册路由和中间件
├── requirements.txt         # Python 依赖
├── routers/
│   ├── materials.py         # 素材 CRUD 接口
│   ├── search.py            # 场景/人物/全文检索接口
│   ├── tags.py              # 标签字典和管理接口
│   └── pipeline.py          # 上传、Pipeline 触发、LLM 配置接口
└── services/
    ├── data_service.py      # 数据访问层（SQLite + YAML）
    └── pipeline_service.py  # Pipeline 执行和状态管理
```

## 数据访问层

`data_service.py` 是唯一的数据访问层，封装了对以下数据源的读取：

| 数据源 | 路径 | 说明 |
|--------|------|------|
| SQLite | `data/material.db` | 场景、人物、标签的索引数据库 |
| index.yaml | `data/index.yaml` | 素材注册清单 |
| tags.yaml | `data/tags.yaml` | 全局标签字典 |
| 小说目录 | `data/novels/{material_id}/` | 每部小说的 YAML 文件 |

小说目录下的文件：

| 文件 | 内容 |
|------|------|
| `meta.yaml` | 元信息（书名、作者、状态） |
| `outline.yaml` | 故事大纲（前提、结构、主题） |
| `worldbuilding.yaml` | 世界观设定 |
| `characters.yaml` | 人物体系（名册、弧线、关系） |
| `tags.yaml` | 小说级标签 |
| `stats.yaml` | 统计报告 |
| `scenes/*.yaml` | 场景文件 |

---

## API 接口清单

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 返回 `{"status": "ok"}` |

---

### 素材 (Materials)

#### `GET /api/materials`

返回所有已注册素材的列表。

**响应示例：**
```json
[
  {
    "id": "nm_novel_20260405_zhbk",
    "type": "novel",
    "name": "《我真没想重生啊》",
    "author": "柳岸花又明",
    "folder": "novels/nm_novel_20260405_zhbk",
    "status": "complete",
    "added": "2026-04-05",
    "scene_count": 884
  }
]
```

#### `GET /api/materials/{material_id}`

返回指定素材的详细元信息，包含数据可用性标记。

**响应字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| material_id | string | 素材 ID |
| name | string | 书名 |
| author | string | 作者 |
| status | string | 状态 (raw / formatted / outlined / tagged / complete / refined) |
| scene_count | number | 场景总数 |
| character_count | number | 人物总数 |
| has_outline | boolean | 是否有大纲 |
| has_worldbuilding | boolean | 是否有世界观 |
| has_characters | boolean | 是否有人物 |
| has_tags | boolean | 是否有标签 |
| has_scenes | boolean | 是否有场景 |
| has_stats | boolean | 是否有统计 |

#### `GET /api/materials/{material_id}/outline`

返回故事大纲。

**响应字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| premise | string | 故事前提 |
| theme | string[] | 主题 |
| tone | string[] | 基调 |
| structure | object[] | 故事结构（分幕） |
| structure[].act | string | 幕名 |
| structure[].title | string | 标题 |
| structure[].chapters | [number, number] | 章节范围 |
| structure[].arc | string | 叙事弧线 |
| structure[].key_event | string | 关键事件 |
| structure[].turning_point | string | 转折点 |
| structure[].pacing_note | string | 节奏提示 |

#### `GET /api/materials/{material_id}/worldbuilding`

返回世界观设定。结构因小说类型而异，可能包含 `power_system`、`geography`、`factions`、`society` 等顶层键。

#### `GET /api/materials/{material_id}/characters`

返回人物体系（读取 YAML 文件）。

**响应字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| roster | object[] | 人物名册 |
| roster[].name | string | 姓名 |
| roster[].aliases | string[] | 别名 |
| roster[].role | string | 角色类型 (protagonist / antagonist / supporting / minor) |
| roster[].description | string | 描述 |
| roster[].traits | string[] | 人物特质 |
| roster[].moral_spectrum | string | 道德光谱 |
| roster[].arc | object[] | 人物弧线阶段 |
| roster[].appearance_count | number | 出场次数 |

#### `GET /api/materials/{material_id}/tags`

返回小说级标签。

**响应字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| genre | string[] | 类型 |
| sub_genre | string[] | 子类型 |
| theme | string[] | 主题 |
| tone | string[] | 基调 |
| narrative | object | 叙事结构 (structure / pov_style / time_handling) |
| style | object | 写作风格 (prose / strength) |
| tropes | string[] | 套路 |

#### `GET /api/materials/{material_id}/scenes`

分页返回场景列表。

**查询参数：**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 (≥1) |
| limit | int | 50 | 每页条数 (1-200) |

**响应：**
```json
{
  "total": 884,
  "page": 1,
  "limit": 50,
  "scenes": [
    {
      "scene_id": "ch0001_s01",
      "chapter": "第一章",
      "title": "场景标题",
      "summary": "场景摘要",
      "tension": 3,
      "characters": ["陈汉升", "萧容鱼"],
      "tags": {
        "scene_type": ["日常"],
        "emotion": ["平静"]
      }
    }
  ]
}
```

#### `GET /api/materials/{material_id}/scenes/{scene_id}`

返回单个场景的完整信息。

#### `GET /api/materials/{material_id}/stats`

返回统计报告。

**响应字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| basic | object | 基础统计 (total_chapters / total_scenes / avg_scenes_per_chapter) |
| scene_type_distribution | object[] | 场景类型分布 (type / count / ratio) |
| emotion_distribution | object[] | 情绪分布 (emotion / count) |
| pacing | object | 节奏统计 |
| pacing.tension_distribution | object | 张力分布 {"1": n, "2": n, ...} |
| pacing.avg_tension | number | 平均张力 |
| pacing.high_tension_scenes | number | 高张力场景数 |
| character_stats | object | 人物统计 (total_indexed / top_10) |
| foreshadowing_stats | object | 钩子统计 (plant_scenes / payoff_scenes) |
| turning_points | object | 转折点 (total_in_outline / key_turning_points[]) |
| technique_stats | object | 技法统计 (techniques_used[]) |

#### `GET /api/materials/{material_id}/stats/html`

返回预生成的统计 HTML 报告（如果存在）。

---

### 检索 (Search)

#### `GET /api/search/scenes`

多维标签检索场景。所有标签参数可选，多条件取交集；无交集结果时自动放宽为取并集排序。

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| scene_type | string | 场景类型 |
| conflict | string | 冲突类型 |
| stakes | string | 赌注 |
| relationship | string | 人物关系 |
| interaction | string | 互动方式 |
| character_moment | string | 弧光时刻 |
| emotion | string | 情绪基调 |
| reader_effect | string | 读者感受 |
| plot_function | string | 情节功能 |
| plot_stage | string | 剧情阶段 |
| technique | string | 叙事技法 |
| dialogue_type | string | 对话类型 |
| info_delivery | string | 信息投放 |
| setting | string | 空间类型 |
| time_weather | string | 时间天气 |
| pacing | string | 节奏型 |
| pov | string | 视角 |
| power_dynamic | string | 权力位差 |
| moral_spectrum | string | 道德光谱 |
| scale | string | 人数规模 |
| character | string | 人物名 |
| material | string | 限定素材 ID |
| tension_min | int | 张力下限 |
| tension_max | int | 张力上限 |
| limit | int | 返回条数 (默认 20, 最大 100) |

**响应：**
```json
{
  "query": { "emotion": "紧张" },
  "total": 15,
  "relaxed": false,
  "results": [
    {
      "scene_id": "ch0450_s01",
      "novel": "《我真没想重生啊》",
      "chapter": "450",
      "title": "修罗场爆发",
      "summary": "...",
      "tension": 5,
      "characters": ["陈汉升", "沈幼楚", "萧容鱼"],
      "tags": { "scene_type": ["争吵"], "emotion": ["紧张"] },
      "matched": ["emotion=紧张"],
      "score": 1.0
    }
  ]
}
```

#### `GET /api/search/characters`

按条件搜索人物。

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| name | string | 模糊搜索名字 |
| archetype | string | 原型 |
| role | string | 角色类型 |
| material | string | 限定素材 ID |
| moral_spectrum | string | 道德光谱 |
| limit | int | 返回条数 |

#### `GET /api/search/text`

按关键词搜索场景标题和摘要。

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| query | string | 搜索关键词（必填） |
| limit | int | 返回条数 |

---

### 全局统计 (Dashboard)

#### `GET /api/stats`

返回仪表盘聚合数据。

**响应字段：**
| 字段 | 说明 |
|------|------|
| novels | 小说总数 |
| scenes | 场景总数 |
| characters | 人物总数 |
| tag_records | 标签记录总数 |
| per_novel | 每部小说的场景数 |
| top_scene_types | 场景类型 Top 15 |
| top_emotions | 情绪 Top 15 |
| tension_distribution | 张力分布 |
| top_techniques | 技法 Top 10 |

---

### 标签 (Tags)

#### `GET /api/tags`

返回全局标签字典（`data/tags.yaml`），按维度组织。

**响应格式：**
```json
{
  "scene_type": {
    "description": "场景的基本类型",
    "values": ["日常", "战斗", "谈判", ...]
  },
  "emotion": {
    "description": "场景的情绪基调",
    "values": ["平静", "紧张", "温馨", ...]
  }
}
```

#### `GET /api/tags/usage`

返回标签使用统计，按维度分组。

#### `POST /api/tags/add`

新增标签值。

**请求体：**
```json
{
  "dimension": "scene_type",
  "value": "新场景类型"
}
```

#### `POST /api/tags/merge`

合并同义标签。将 source 标签合并到 target，同时更新 SQLite 中的记录。

**请求体：**
```json
{
  "dimension": "emotion",
  "source": "紧张不安",
  "target": "紧张"
}
```

---

### 上传与 Pipeline

#### `POST /api/upload`

上传小说文件。支持 `.txt` / `.md` / `.epub`。

**请求：** `multipart/form-data`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | File | 是 | 小说文件 |
| name | string | 否 | 书名（默认从文件名提取） |
| author | string | 否 | 作者（默认"未知"） |

**响应：**
```json
{
  "material_id": "nm_novel_20260409_a1b2",
  "name": "书名",
  "message": "上传成功，可以开始 pipeline"
}
```

#### `GET /api/pipeline/{material_id}/status`

获取 Pipeline 执行状态。

**响应：**
```json
{
  "stages_completed": ["ingest", "format"],
  "running": false,
  "current_stage": null,
  "last_error": null,
  "updated_at": "2026-04-09T10:30:00"
}
```

#### `POST /api/pipeline/{material_id}/trigger`

触发 Pipeline 指定阶段。后台异步执行。

**查询参数：**
| 参数 | 说明 |
|------|------|
| stage | 阶段名: `ingest` / `format` / `build-index` / `analyze` / `scenes` / `finalize` |

> `analyze`、`scenes`、`finalize` 需要配置 LLM API。

---

### LLM 设置

#### `GET /api/settings/llm`

获取 LLM 配置（不返回 API Key 明文）。

#### `PUT /api/settings/llm`

保存 LLM 配置。

**请求体：**
```json
{
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "model": "gpt-4o"
}
```

#### `POST /api/llm/proxy`

代理 LLM 聊天补全请求，使用后端保存的 API 配置。

**请求体：**
```json
{
  "messages": [{"role": "user", "content": "你好"}],
  "model": "gpt-4o",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

---

## 错误码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 冲突（如 Pipeline 已在运行） |
| 500 | 服务器内部错误 |
