# 前端文档

## 概述

前端基于 **React 19 + TypeScript + Vite** 构建，使用 **Tailwind CSS v4** 做样式、**TanStack Query** 做数据管理、**ECharts** 做可视化图表。整体为深色主题的单页应用 (SPA)。

- 开发地址: `http://127.0.0.1:5173`
- API 代理: 开发模式下直接请求 `http://127.0.0.1:8000/api`，生产模式下走 `/api` 代理

## 快速启动

```bash
cd frontend
npm install
npm run dev
```

> 需要先启动后端 `cd backend && python main.py`

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| TypeScript | 6 | 类型安全 |
| Vite | 8 | 构建工具 |
| Tailwind CSS | 4 | 原子化 CSS |
| TanStack Query | 5 | 异步状态管理 + 请求缓存 |
| React Router | 7 | 客户端路由 |
| ECharts | 6 | 图表可视化 |
| Lucide React | 1.7 | 图标库 |

## 项目结构

```
frontend/
├── index.html               # 入口 HTML
├── vite.config.ts            # Vite 配置（代理、别名、插件）
├── tsconfig.app.json         # TypeScript 配置
├── package.json              # 依赖管理
└── src/
    ├── main.tsx              # React 入口，挂载到 #root
    ├── App.tsx               # 根组件：路由、QueryClient、ErrorBoundary
    ├── index.css             # 全局样式（Tailwind 导入 + 主题）
    ├── api/
    │   └── client.ts         # API 客户端（所有后端请求封装）
    ├── types/
    │   └── index.ts          # TypeScript 接口定义
    ├── lib/
    │   └── utils.ts          # 工具函数（cn、TAG_COLORS、STATUS_MAP、TAG_LAYERS）
    ├── components/
    │   └── Layout.tsx        # 全局布局（侧边栏 + 主内容区）
    └── pages/
        ├── Dashboard.tsx     # 仪表盘（总览统计 + 图表）
        ├── MaterialList.tsx  # 素材列表（卡片网格）
        ├── MaterialDetail.tsx # 素材详情（多 Tab：概览/大纲/世界观/人物/标签/场景/统计）
        ├── SceneSearch.tsx   # 场景搜索（标签多选 + 全文搜索双模式）
        ├── CharacterSearch.tsx # 人物搜索（条件筛选 + 人物卡片）
        ├── TagDictionary.tsx # 标签字典（展开/收起 + 新增/合并管理）
        ├── Upload.tsx        # 上传小说（拖拽 + 元信息填写）
        └── Settings.tsx      # 设置（LLM API 配置）
```

## 路由表

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | Dashboard | 仪表盘首页 |
| `/materials` | MaterialList | 素材列表 |
| `/materials/:id` | MaterialDetail | 素材详情 |
| `/search/scenes` | SceneSearch | 场景搜索 |
| `/search/characters` | CharacterSearch | 人物搜索 |
| `/tags` | TagDictionary | 标签字典 |
| `/upload` | Upload | 上传小说 |
| `/settings` | Settings | 系统设置 |

所有页面使用 `React.lazy()` 懒加载，包裹在 `ErrorBoundary` 中。

---

## 页面功能详述

### Dashboard（仪表盘）

数据来源: `GET /api/stats`

展示内容：
- 四个数字卡片：小说总数、场景总数、人物总数、标签记录数
- 场景类型 Top 10 饼图 (ECharts)
- 张力分布柱状图 (ECharts)
- 情绪 Top 10 条形图
- 每部小说场景数对比

### MaterialList（素材列表）

数据来源: `GET /api/materials`

- 卡片网格展示所有素材
- 每张卡片显示：书名、作者、状态标签、场景数、添加日期
- 点击卡片跳转到详情页

### MaterialDetail（素材详情）

数据来源: 多个 API 按需加载

7 个 Tab 页：

| Tab | API | 渲染方式 |
|-----|-----|----------|
| 概览 | `GET /api/pipeline/{id}/status` + `GET /api/materials/{id}/stats` | Pipeline 操作面板 + 核心指标（张力分布迷你图）+ 数据可用性 |
| 大纲 | `GET /api/materials/{id}/outline` | 故事前提 + 主题/基调标签 + 时间线式故事结构 |
| 世界观 | `GET /api/materials/{id}/worldbuilding` | 按分类（力量体系/地理/势力等）卡片展示 |
| 人物 | `GET /api/materials/{id}/characters` | 人物卡片（角色图标 + 别名 + 特质标签 + 弧线时间线 + 出场统计） |
| 标签 | `GET /api/materials/{id}/tags` | 分组 badge（类型/主题/基调/文笔/套路/叙事结构） |
| 场景 | `GET /api/materials/{id}/scenes` | 可展开的场景列表，带分页，展开显示摘要/人物/标签 |
| 统计 | `GET /api/materials/{id}/stats` | 数字卡片 + 张力柱状图 + 场景类型饼图 + 情绪条形图 + 人物 Top 10 + 转折点时间线 + 钩子统计 + 写作技法标签 |

**Pipeline 操作面板：**
- 四个可触发按钮：入库检查 / 格式清洗 / 构建索引 / 分析(LLM)
- 自动轮询运行状态（3 秒间隔）
- 完成状态绿色标记，运行中显示加载动画
- 错误信息红色提示

### SceneSearch（场景搜索）

双模式切换（顶部 Tab）：

**标签搜索模式：**
- 左侧固定筛选栏：
  - 人物名输入框
  - 张力范围（最小/最大值）
  - 6 大标签层级（A 内容层 ~ F 物理层），每层内多维度
  - 每个维度下所有标签值以**可点击 checkbox** 形式呈现（支持多选）
  - 已选标签高亮并带勾号，层级标题旁有选中指示
- 右侧结果区：独立滚动
- 结果卡片：场景 ID、标题、张力、来源小说/章节、摘要、匹配标签（绿色）、全部标签（按维度着色）、出场人物

**全文搜索模式：**
- 搜索框 + 回车触发
- 结果卡片展示同上

数据来源: `GET /api/search/scenes` / `GET /api/search/text`

### CharacterSearch（人物搜索）

条件筛选：人物名（模糊）、角色类型、原型、道德光谱

人物卡片展示：
- 角色图标（主角=心、反派=剑、配角/龙套=人形）
- 姓名、角色标签、原型标签
- 来源小说
- 道德光谱、叙事功能、出场次数
- 心理特征标签（致命缺陷/执念/软肋/误信）
- 可展开的**人物弧线**时间线（阶段/状态/触发事件/章节号）

> `arc_summary` 字段在 SQLite 中存为 Python list 字符串，前端自动解析为结构化数据。

数据来源: `GET /api/search/characters`

### TagDictionary（标签字典）

数据来源: `GET /api/tags` + `GET /api/tags/usage`

- 按 6 个层级 + 小说级标签分组展示
- 每个维度可展开，显示：描述、所有标签值（带使用次数）
- **管理功能：**
  - 「新增」按钮 → 内联输入框添加标签值
  - 「合并」按钮 → 选择源标签和目标标签合并（同步更新数据库）

### Upload（上传小说）

- 拖拽或点击选择文件（.txt / .md / .epub）
- 填写书名和作者（书名默认从文件名提取）
- 上传成功后显示 material_id，可直接跳转详情页

数据来源: `POST /api/upload`

### Settings（系统设置）

- LLM API 配置：Base URL、API Key（密码遮罩）、模型名
- 保存时同步写入 localStorage 和后端（`PUT /api/settings/llm`）
- 测试连接功能（调用 `/models` 接口验证）
- 后端服务状态显示

---

## API 客户端

所有后端请求封装在 `src/api/client.ts` 的 `api` 对象中：

| 方法 | 对应 API |
|------|----------|
| `api.getStats()` | `GET /api/stats` |
| `api.listMaterials()` | `GET /api/materials` |
| `api.getMaterial(id)` | `GET /api/materials/{id}` |
| `api.getOutline(id)` | `GET /api/materials/{id}/outline` |
| `api.getWorldbuilding(id)` | `GET /api/materials/{id}/worldbuilding` |
| `api.getCharacters(id)` | `GET /api/materials/{id}/characters` |
| `api.getNovelTags(id)` | `GET /api/materials/{id}/tags` |
| `api.getScenes(id, page, limit)` | `GET /api/materials/{id}/scenes` |
| `api.getScene(id, sceneId)` | `GET /api/materials/{id}/scenes/{sceneId}` |
| `api.getMaterialStats(id)` | `GET /api/materials/{id}/stats` |
| `api.searchScenes(filters)` | `GET /api/search/scenes` |
| `api.searchCharacters(filters)` | `GET /api/search/characters` |
| `api.searchText(query, limit)` | `GET /api/search/text` |
| `api.getTagDict()` | `GET /api/tags` |
| `api.getTagUsage()` | `GET /api/tags/usage` |
| `api.addTag(dimension, value)` | `POST /api/tags/add` |
| `api.mergeTags(dimension, source, target)` | `POST /api/tags/merge` |
| `api.uploadNovel(file, name?, author?)` | `POST /api/upload` |
| `api.getPipelineStatus(id)` | `GET /api/pipeline/{id}/status` |
| `api.triggerPipeline(id, stage)` | `POST /api/pipeline/{id}/trigger` |
| `api.getLlmSettings()` | `GET /api/settings/llm` |
| `api.saveLlmSettings(cfg)` | `PUT /api/settings/llm` |

---

## 数据缓存策略

通过 TanStack Query 管理：
- `staleTime`: 5 分钟（避免频繁请求）
- `refetchOnWindowFocus`: 关闭
- Pipeline 运行期间自动 3 秒轮询状态
- 标签新增/合并后手动 `invalidateQueries` 刷新

---

## 标签体系

6 个场景标签层级（20 个维度），前端在 `src/lib/utils.ts` 中定义：

| 层级 | 维度 | 配色 |
|------|------|------|
| A. 内容层 | scene_type / conflict / stakes | 玫红 |
| B. 人物层 | relationship / interaction / power_dynamic / character_moment / moral_spectrum | 紫色 |
| C. 情感层 | emotion / reader_effect | 琥珀 |
| D. 结构层 | plot_stage / plot_function / pacing | 蓝色 |
| E. 技法层 | technique / dialogue_type / pov / info_delivery | 翠绿 |
| F. 物理层 | setting / scale / time_weather | 青色 |

另有 G. 小说级标签：genre / tone / narrative_structure / time_handling / prose_style / writing_strength / tropes（粉色）

---

## 类型定义

核心 TypeScript 接口定义在 `src/types/index.ts`：

| 接口 | 说明 |
|------|------|
| `Material` | 素材列表项 |
| `MaterialDetail` | 素材详情（含数据可用性标记） |
| `PipelineStatus` | Pipeline 状态 |
| `PipelineStatusResponse` | Pipeline API 响应 |
| `DashboardStats` | 仪表盘统计数据 |
| `SceneItem` | 场景数据 |
| `ScenesResponse` | 分页场景列表 |
| `SceneSearchResponse` | 场景搜索结果 |
| `CharacterItem` | 人物数据 |
| `CharacterSearchResponse` | 人物搜索结果 |
| `TextSearchResponse` | 全文搜索结果 |
| `TagDimension` | 标签维度定义 |
| `TagDictionary` | 标签字典 |
| `TagUsage` | 标签使用统计 |

---

## 构建部署

```bash
cd frontend
npm run build      # 产出到 dist/
npm run preview    # 本地预览生产构建
```

生产环境下需将 `/api` 反向代理到后端服务。Nginx 配置示例：

```nginx
server {
    listen 80;
    root /path/to/frontend/dist;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
    }
}
```
