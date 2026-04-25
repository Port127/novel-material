---
name: pipeline-events
description: 在素材分析完成后执行全书事件拆分、索引构建与完整性验证；用于大书的可恢复长流程
---

# 任务

执行事件阶段的完整闭环：

1. `novel-events all`
2. `build-index`
3. 实体提取与完整性验证
4. 若被阻断，明确转交 `ai-backfill`

这是整个系统里最重的阶段，默认按**自动分批 + 持久化进度 + 可跨对话恢复**执行。

## 适用边界

用于：
- `status=tagged` 后开始全书事件拆分
- events 已部分完成，需要恢复
- events 已完成，但索引 / 完整性验证 / 补录未完成

不用于：
- 单批章节手动事件拆分（交给 `novel-events`）
- refine / stats 阶段

## 输入

- `material_id`

## 阻断条件

进入本 skill 前先检查：

| 条件 | 行为 |
|------|------|
| `status = backfill-blocked` | 拒绝执行，提示先完成 `ai-backfill`，不要继续本阶段 |
| 缺少 `outline/_index.yaml` 或 `characters/_index.yaml` | 拒绝执行，先回到 `pipeline-analyze` |

## 默认执行路径

### 1. 判断恢复点

先看真实文件，再看 `meta.yaml`：

| 真实状态 | 本次动作 |
|----------|----------|
| `events/` 不存在或为空 | 从 `novel-events all` 开始 |
| `events/` 部分完成 | 从未覆盖章节继续 `novel-events all` |
| events 已全，`events_index.yaml` 缺失 | 跳过事件生成，直接 `build-index` |
| 索引已建，`source_entities.json` 缺失 | 继续实体提取 |
| `source_entities.json` 有，`completeness_report.yaml` 缺失 | 继续完整性验证 |
| 完整性报告显示被阻断，且 `backfill_done != true` | 停止本阶段，提示执行 `ai-backfill` |
| 完整性已通过 | 结束本阶段，等待 `pipeline-finalize` |

### 2. 执行 `novel-events all`

调用 `../novel-events/SKILL.md`，要求：

- 自动循环分批，不逐批询问
- 每批写入后立即执行：

```bash
python scripts/core/quality_audit.py {material_id} --batch {本批范围}
```

**`--batch` 只传本批范围**，例如 `181-200`，禁止传累计范围。

分批阶段的最低要求：

- 只读当前批相关原文
- 立即落盘事件 YAML
- 立即审计
- 立即更新 `meta.yaml` 进度

### 3. 全书质量门控

events 全部写完后，进入 `build-index` 前必须运行：

```bash
python scripts/core/quality_audit.py {material_id}
```

如果出现以下情况，**禁止继续**：

| 条件 | 行为 |
|------|------|
| 主线事件密度 `< 0.25` | 强制补切 |
| 连续未覆盖章节 `> 3` | 强制补切 |

### 4. 构建索引

调用 `../build-index/SKILL.md`，生成：

- `events_manifest.yaml`
- `events_index.yaml`
- SQLite 索引
- 全局聚合索引

开始 build-index 前，先把中间状态写入 `meta.yaml`，避免中途断掉后重复跑 events。

### 5. 实体提取与完整性验证

依次运行：

```bash
python scripts/core/extract_source_entities.py {material_id}
python scripts/core/validate_completeness.py {material_id}
```

产物：

- `source_entities.json`
- `completeness_report.yaml`

### 6. 完整性门控

`validate_completeness.py` 的真实阻断规则优先于人工推断：

| 条件 | 行为 |
|------|------|
| `completeness_score < fail_threshold` | 脚本自动写 `status=backfill-blocked` 并退出非零 |
| `critical_count > 0` | 即使分数达标，也会被脚本阻断并写 `status=backfill-blocked` |
| 两者都不满足 | 通过，结束本阶段 |

### 7. 被阻断后的下一步

如果完整性验证返回阻断：

1. 停止当前 `pipeline-events`
2. 明确报告：
   - `completeness_score`
   - `critical_count`
   - 状态已被脚本写成 `backfill-blocked`
3. 下一步提示用户执行 `../ai-backfill/SKILL.md`
4. `ai-backfill` 完成后，再重新进入 `pipeline-events` 做：
   - `build-index`
   - `validate_completeness.py`

## 恢复与分段

- 大书默认允许跨对话恢复
- 每批完成后立即写状态
- 不在同一轮消息里要求“继续下一批”
- 如果上下文已明显膨胀，直接输出恢复命令，不做空转对话

## 输出要求

报告至少包含：

- 本次从哪一步恢复
- 完成了哪些步骤
- 当前章节覆盖与事件数量
- 是否通过完整性门控
- 若被阻断，脚本写回了什么状态、下一步必须执行什么

## 仅在需要时读取

- `../_shared/references/skill-conventions.md`
- `references/recovery.md`
- `references/completeness-gates.md`
- `../novel-events/SKILL.md`
- `../build-index/SKILL.md`
- `../ai-backfill/SKILL.md`
- `../../../AGENTS.md`
