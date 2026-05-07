# 日志系统规范

本文档定义 novel-material 日志系统的配置、级别使用规范和最佳实践。

## 环境变量配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LOG_LEVEL` | `INFO` | 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `LOG_DIR` | `logs` | 日志目录（相对于项目根目录） |
| `LOG_MAX_FILES` | `100` | 保留日志文件数量（超过自动清理，设为 0 禁用清理） |

### 使用示例

```bash
# 开发调试模式
LOG_LEVEL=DEBUG nm pipeline analyze nm_novel_20260507_abc1

# 减少日志保留数量
LOG_MAX_FILES=10 nm pipeline full novel.txt

# 自定义日志目录
LOG_DIR=/var/log/novel-material nm pipeline full novel.txt
```

## 日志级别规范

### DEBUG

**何时使用**：
- 开发调试时查看详细信息
- 性能分析、中间数据检查
- 问题诊断时需要详细追踪

**示例**：
- 向量化前 10 个值
- API 调用的完整 prompt/response（仅在排查问题时）
- 阶段内部详细执行步骤

**注意**：DEBUG 级别通常不在生产环境显示，会输出大量信息影响可读性。

### INFO（默认）

**何时使用**：
- 正常运行状态记录
- 关键节点进度
- 业务数据统计

**示例**：
- API 调用成功：`[章节分析#批次261-265] API: 2.5s | in=1800 out=450 total=2250`
- 阶段开始/完成：`=== 阶段开始: [1/4] 章节分析 ===`
- 小说信息：`小说: 《凡人修仙传》 | 1327 章 | 2.1M 字`
- 批次进度：`[批次 53/266] 第 261-265 章`

### WARNING

**何时使用**：
- 可自动恢复的问题
- 需要关注但不影响流程继续
- 资源使用接近阈值

**示例**：
- 单章分析失败跳过：`第 120 章分析失败，降级为单章模式`
- 速率限制等待：`速率限制（429），等待 60s`
- 质量警告：`摘要合格率 85%（低于 90%）`
- 新标签候选：`发现新标签候选: element/xxx`

### ERROR

**何时使用**：
- 需人工关注的失败
- 非预期错误（重试耗尽后）
- 数据质量问题

**示例**：
- API 连续失败：`API 失败: APIStatusError: 连续 8 次重试耗尽`
- 质量校验不通过：`章级分析质量校验未通过`
- 配置错误：`meta.yaml 不存在`

### CRITICAL

**何时使用**：
- 流程必须终止
- 基础设施不可用
- 配置缺失无法运行

**示例**：
- 数据库不可用：`DATABASE_URL 未配置`
- 存储空间不足：`磁盘空间不足，无法写入日志`
- 权限错误：`无法创建日志目录`

## 日志文件管理

### 文件命名

```
logs/pipeline_{YYYYMMDD_HHMMSS}.log
```

示例：
- `logs/pipeline_20260507_151856.log`
- `logs/pipeline_20260507_175356.log`

### 清理机制

每次 CLI 启动时自动清理：
- 保留最新的 `LOG_MAX_FILES` 个日志文件
- 按修改时间排序，删除最旧的

### 单个运行日志结构

```
15:18:58 [INFO] pipeline: 小说: 《凡人修仙传》 | 1327 章 | 2.1M 字 | 状态: clean
15:18:58 [INFO] pipeline: === 阶段开始: [1/4] 章节分析 ===
15:21:15 [INFO] pipeline: [章节分析#批次1-5] API: 2.5s | in=1800 out=450 total=2250
15:24:07 [INFO] pipeline: [章节分析#批次6-10] API: 2.8s | in=1800 out=480 total=2280
15:24:07 [WARNING] pipeline: 速率限制（429），等待 60s
...
15:42:00 [INFO] pipeline: 阶段完成: 章节分析 | elapsed=15120s | tokens_in=2386000 tokens_out=595000 | api_calls=266
```

## 日志与进度条的关系

### CLI 运行时

- **进度条**：Rich 进度条显示实时进度（阶段名、进度、ETA）
- **日志暂停**：`pause_console_logging()` 暂停控制台输出，避免干扰进度条
- **日志恢复**：`resume_console_logging()` 恢复控制台输出

### 日志文件

- **始终写入**：无论控制台是否暂停，日志文件持续记录
- **完整记录**：包含所有级别、所有阶段、所有 API 调用

## 最佳实践

### 1. 开发调试

```bash
LOG_LEVEL=DEBUG nm pipeline analyze <material_id>
```

查看详细的 API 调用、中间数据。

### 2. 生产运行

```bash
LOG_LEVEL=INFO LOG_MAX_FILES=100 nm pipeline full <novel.txt>
```

默认级别，保留足够历史但不过多。

### 3. 问题排查

```bash
LOG_LEVEL=DEBUG LOG_MAX_FILES=10 nm pipeline continue <material_id>
```

保留少量日志但详细，用于诊断问题。

### 4. 成本监控

定期查看 run_history.yaml：
```yaml
tokens_in: 2500000
tokens_out: 650000
estimated_cost: 1.62
```

## 初始化脚本

以下脚本使用 `print` 而非 logger，原因是：
- 一次性操作，需要即时反馈
- 不是流水线的一部分

| 脚本 | 说明 |
|------|------|
| `init_db.py` | 数据库初始化 |
| `init_tags.py` | 标签数据导入 |
| `init_data.py` | 基础数据初始化 |

这些脚本输出不写入 pipeline 日志文件，避免混淆。

## 常见问题

### Q: 日志文件太多怎么办？

设置 `LOG_MAX_FILES`：
```bash
LOG_MAX_FILES=20 nm pipeline full novel.txt
```

### Q: 想看 API 调用详情怎么办？

设置 DEBUG 级别：
```bash
LOG_LEVEL=DEBUG nm pipeline analyze material_id
cat logs/pipeline_*.log | grep "API:"
```

### Q: 如何统计成本？

查看 `run_history.yaml`：
```bash
cat novels/<material_id>/run_history.yaml | grep "estimated_cost"
```