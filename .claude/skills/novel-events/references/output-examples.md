# 输出示例（抽象占位）

## 线程清单

```yaml
threads:
  - id: main
    description: 主角核心叙事线
  - id: romance_角色A
    description: 与角色A相关的感情线
  - id: subplot_地点B
    description: 围绕地点B展开的支线
```

## 事件草案

```yaml
thread: main
events:
  - id: ev_main_001
    title: 主角第一次卷入冲突
    chapters: ['第1章', '第2章']
```

## 正式事件

```yaml
id: ev_main_001
thread: main
chapter: '第1章'
chapters: ['第1章', '第2章']
title: 主角第一次卷入冲突
summary: '主角因一次意外被迫进入更大的局势。'
outcome: '主角决定主动追查幕后原因。'
lines: [120, 268]
lines_approximate: false
tags:
  event_type: [卷入]
  conflict: [外部压力]
```
