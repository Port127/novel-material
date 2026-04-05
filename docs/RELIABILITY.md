# Novel Material 可靠性

## 数据可靠性

### YAML 格式验证

所有索引文件使用 YAML 格式，需验证：
- 语法正确
- 字段完整
- ID 唯一

### 备份策略

- Git 版本控制
- 素材原文不可变（只增不改）

## Skill 可靠性

### 输入验证

每个 skill 验证输入：
- 必填参数检查
- 类型检查
- 路径存在检查

### 输出验证

- YAML 写入验证
- 索引完整性检查
- ID 格式检查

## 检索可靠性

### 索引一致性

- 全局索引与小说级数据一致性
- 场景标签与 tags.yaml 字典一致性
- 人物索引与人物体系一致性

### 检索准确性

待 Eval Suite 建立：
- 关键词检索命中率
- 多维标签匹配准确率

## 故障恢复

### 素材丢失

从原文重新入库，使用 `/material-add`

### 索引损坏

重新执行对应 skill：
- `/novel-outline [素材ID]`
- `/novel-characters [素材ID]`
- `/novel-scenes [素材ID] [章节范围 | all]`

### 标签混乱

使用标签治理 skills：
- `/tag-add [维度] [值]`
- `/tag-merge [旧值] [新值]`

## Related Docs

- [AGENTS.md](../AGENTS.md)
- [docs/QUALITY_SCORE.md](QUALITY_SCORE.md)