# 素材分类功能执行方案

> 本文档记录素材分类功能的设计决策和实施步骤，用于指导后续开发。

## 相关文档

- [ARCHITECTURE.md](../ARCHITECTURE.md) — 系统架构与数据流
- [REQUIREMENTS.md](REQUIREMENTS.md) — 项目需求边界
- [USER_MANUAL.md](USER_MANUAL.md) — 使用手册

---

## 一、问题背景

### 1.1 当前状态

| 维度 | 数据 |
|------|------|
| material 素材库 | **1849本**（知轩藏书） |
| 已入库 | **8本** |
| 全量入库耗时 | 每本约 5-6 小时（LLM 分析） |

### 1.2 用户需求

用户需要**按需入库**而非全量入库：

1. 检索某个类型（如"玄幻修仙"）的小说
2. 查询已入库数量
3. 若少于 50 本 → 从 material 素材库搜索候选
4. 返回候选列表 → 用户选择后执行入库

### 1.3 核心障碍

`novel_index.json` 只有书名、作者、下载量，**无 genre 分类信息**。无法按类型筛选未入库素材。

---

## 二、解决方案：LLM 分类

### 2.1 方案对比

| 方案 | 时间 | 成本 | 精度 |
|------|------|------|------|
| A：书名关键词推断 | 0 | 0 | 低（"龙族"实际是奇幻而非玄幻） |
| **B：LLM 分析前3章** | 2-4小时 | ~50元（可用免费额度抵扣） | 高 |

**决策：采用方案B**

### 2.2 成本估算

以单本书前3章分类为例：

| 项目 | 单本书估算 |
|------|----------|
| 输入 tokens | 3000-4000 |
| 输出 tokens | 500-1000 |
| thinking tokens | 1500-2000 |
| 单次请求时间 | 30-50秒 |

1849本书总成本：

| 项目 | 计算 | 金额 |
|------|------|------|
| 输入 tokens | 1849 × 4000 = 7.4M | 7.4 × 0.8 = 5.9元 |
| 输出 tokens (含thinking) | 1849 × 3000 = 5.5M | 5.5 × 8 = 44元 |
| **总计** | | **≈50元** |

阿里云百炼免费额度：**7000万 tokens**（90天有效），可覆盖全部成本。

---

## 三、架构设计

### 3.1 文件位置

```
src/novel_material/
├── cli/
│   └── material.py      ← 新增 classify 命令
├── material/
│   ├── import_material.py
│   ├── delete.py
│   └── classify.py      ← 新增：分类逻辑
└── infra/
    └── ...              ← 复用现有基础设施（LLM、YAML）

data/
├── material_index.yaml    ← 新增：分类结果索引
├── classify_progress.yaml ← 新增：进度文件
└── ...
```

### 3.2 耦合关系

分类模块**仅依赖 infra**，与其他业务模块无耦合：

```
                  ┌─────────────┐
                  │   infra/    │
                  │ (LLM/YAML)  │
                  └──────┬──────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
    ┌────┴────┐    ┌─────┴─────┐   ┌─────┴─────┐
    │material │    │  pipeline │   │ classify  │
    │(现有)   │    │  (现有)   │   │(新增)    │
    └─────────┘    └───────────┘   └───────────┘
```

**不依赖：**
- pipeline（不跑流水线）
- storage（不入数据库）
- validation（不校验）
- search（不检索）
- schema/prompts（分类提示词独立，不入契约层）

---

## 四、数据结构设计

### 4.1 分类结果索引

路径：`data/material_index.yaml`

```yaml
materials:
  0001_凡人修仙传:
    title: 凡人修仙传
    author: 未知
    file_path: material/知轩藏书/仙草排行榜-前2000/0001_凡人修仙传.txt
    file_size: 15072456
    download_count: 8306
    genre:
      - 玄幻
      - 修仙
    genre_description: 传统修仙升级流，凡人逆袭成仙
    classification_status: done
    classification_time: 2026-05-14T10:00:00
  0002_极道天魔:
    title: 极道天魔
    author: 滚开
    ...
```

**设计理由：**
- 与原始 `novel_index.json` 分离，避免污染爬虫数据
- 符合现有 `data/index.yaml` 的 YAML 格式风格
- 支持后续按 genre 查询

### 4.2 进度文件

路径：`data/classify_progress.yaml`

```yaml
last_processed_sequence: 150
last_processed_file: 0002_极道天魔.txt
last_processed_time: 2026-05-14T12:30:00
total: 1849
remaining: 1699
failed:
  - sequence: 88
    reason: "文件不存在"
```

**设计理由：**
- 逐条处理，处理完立即写入结果
- 进度文件独立，崩溃后可从断点恢复
- 记录失败条目，支持批量重试

---

## 五、CLI 命令设计

### 5.1 命令列表

```bash
nm classify start              # 启动分类（从进度文件恢复）
nm classify status             # 查看进度统计
nm classify retry --seq 88     # 重试单条失败的
nm classify retry --failed     # 重试所有失败的
nm classify clean              # 清空进度，重新开始
```

### 5.2 命令行为

**`nm classify start`：**

1. 载入 `classify_progress.yaml`（不存在则从 sequence=1 开始）
2. 读取 `novel_index.json` 获取素材列表
3. 从 `last_processed_sequence + 1` 开始循环：
   - 读取 txt 文件前3章（约 5000-8000 字）
   - 调用 LLM 生成 genre 分类
   - 写入 `material_index.yaml`
   - 更新 `classify_progress.yaml`
4. 遇到错误时：
   - 记录到 `failed` 列表
   - 继续处理下一本（不中断）

**`nm classify status`：**

```
分类进度统计
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总素材数:    1849
已完成:      150 (8.1%)
剩余:        1699
失败:        0
当前处理:    0002_极道天魔.txt
开始时间:    2026-05-14 12:00
预计剩余:    ~2.5小时
```

---

## 六、LLM 提示词设计

### 6.1 提示词模板

位置：`src/novel_material/material/classify_prompt.py`（硬编码，不入契约层）

```python
SYSTEM_PROMPT = """
你是小说类型分类专家。根据小说前三章内容，判断其 genre 类型。

输出格式（JSON）：
{
  "genre": ["主类型", "子类型"],
  "genre_description": "一句话描述小说类型特点",
  "confidence": 0.8
}

genre 取值范围：
- 玄幻（含修仙、东方玄幻）
- 奇幻（含西幻、魔幻）
- 科幻
- 都市（含都市异能、都市言情）
- 历史（含历史架空）
- 武侠
- 仙侠
- 游戏（含网游、电竞）
- 悬疑（含推理、惊悚）
- 其他

confidence 取值：0.0-1.0，表示分类置信度
"""

USER_PROMPT_TEMPLATE = """
小说标题：{title}
作者：{author}

前三章内容：
{content}

请分析并输出分类结果。
"""
```

### 6.2 输出校验

- genre 必须在预定义取值范围内
- confidence < 0.6 时标记为 `classification_status: low_confidence`
- JSON 解析失败时记录错误，继续下一本

---

## 七、实施步骤

### 7.1 开发任务清单

| 序号 | 任务 | 预估时间 | 依赖 |
|------|------|----------|------|
| 1 | 创建 `material/classify.py` 核心逻辑 | 1h | 无 |
| 2 | 创建 `material/classify_prompt.py` 提示词 | 0.5h | 无 |
| 3 | 扩展 `cli/material.py` 添加命令 | 0.5h | 1 |
| 4 | 编写单元测试 | 0.5h | 1,2,3 |
| 5 | 手动测试（小批量） | 0.5h | 4 |
| 6 | 全量执行分类 | 2-4h | 5 |

**总开发时间：约 3小时**

### 7.2 验收标准

1. `nm classify start` 可正常启动，从断点恢复
2. `nm classify status` 正确显示进度
3. 处理失败不中断流程，记录到 failed 列表
4. `material_index.yaml` 格式正确，可按 genre 查询
5. 全量执行完成，覆盖率 > 95%

---

## 八、后续功能预留

分类完成后，支持以下后续功能（本文档不覆盖实施细节）：

| 功能 | 描述 | 依赖 |
|------|------|------|
| 按需入库 | 检索 genre + 查询已入库数量 + 返回候选 | 分类结果 + 数据库 |
| 入库优先级 | 按下载量 / quality 评分排序候选 | 分类结果 |
| 分类结果同步 | 将 material_index.yaml 同步到数据库 | storage 模块 |

---

## 九、风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| LLM API 限流 | 处理中断 | 自动重试 + 进度文件 |
| 文件不存在 | 单条失败 | 记录 failed 列表 + 继续 |
| 分类精度不足 | 后续检索质量差 | confidence < 0.6 标记 + 人工审核 |
| 提示词偏移 | 输出格式错误 | JSON schema 校验 + 重试 |

---

## 十、决策记录

| 决策点 | 选择 | 理由 |
|------|------|------|
| 分类方案 | LLM 分析前3章 | 精度高，成本可控 |
| 输出位置 | `material_index.yaml` | 与原始数据分离，符合现有风格 |
| 断点续传 | 进度文件 + 逐条写入 | 简单可靠，崩溃可恢复 |
| 是否入库 | 先不入 | 分类阶段保持轻量，后续功能再考虑 |
| 提示词位置 | 独立文件，不入契约层 | 分类是前置环节，不入核心架构 |