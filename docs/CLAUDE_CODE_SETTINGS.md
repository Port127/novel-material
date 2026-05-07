# Claude Code 配置指南

本文档详细介绍 Claude Code 的 `settings.json` 配置文件，涵盖所有可用配置项、参数说明、默认值和使用示例。

---

## 目录

1. [配置文件位置与优先级](#配置文件位置与优先级)
2. [核心配置](#核心配置)
3. [环境变量配置](#环境变量配置)
4. [权限与安全配置](#权限与安全配置)
5. [沙箱配置](#沙箱配置)
6. [MCP 服务器配置](#mcp-服务器配置)
7. [钩子配置](#钩子配置)
8. [UI/显示配置](#ui显示配置)
9. [插件配置](#插件配置)
10. [代理配置](#代理配置)
11. [存储与清理配置](#存储与清理配置)
12. [企业策略配置](#企业策略配置)
13. [其他配置](#其他配置)
14. [环境变量参考](#环境变量参考)

---

## 配置文件位置与优先级

### 配置文件位置

Claude Code 支持多层级配置文件，按优先级从低到高：

| 位置 | 文件路径 | 作用域 |
|------|----------|--------|
| 全局用户配置 | `~/.claude/settings.json` | 所有项目 |
| 项目配置 | `<project>/.claude/settings.json` | 当前项目 |
| 本地配置 | `<project>/.claude/settings.local.json` | 当前项目（不提交到 git） |
| 企业策略配置 | `managed-settings.json` 或 `managed-settings.d/` | 企业管理 |

### 配置优先级

配置项的优先级规则（从高到低）：

1. **命令行参数**（如 `--model`, `--effort`）
2. **本地配置** (`settings.local.json`)
3. **项目配置** (`settings.json`)
4. **企业策略配置** (`managed-settings.json`)
5. **全局用户配置** (`~/.claude/settings.json`)
6. **默认值**

> 注意：企业策略配置中的 `deny` 规则具有最高优先级，无法被用户配置覆盖。

---

## 核心配置

### model

指定默认使用的 Claude 模型。

```json
{
  "model": "sonnet"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | string | `"sonnet"` | 模型别名或完整模型 ID |

**可选值：**

| 值 | 说明 |
|----|------|
| `"sonnet"` | Claude Sonnet 4.6（平衡性能与速度） |
| `"opus"` | Claude Opus 4.7（最强智能） |
| `"haiku"` | Claude Haiku 4.5（最快响应） |
| `"claude-opus-4-7"` | Opus 4.7 完整 ID |
| `"claude-sonnet-4-6"` | Sonnet 4.6 完整 ID |
| `"claude-haiku-4-5-20251001"` | Haiku 4.5 完整 ID |
| `"glm-5"` | 第三方模型（如阿里云 GLM） |

**运行时切换：**
```bash
claude --model opus    # 临时使用 Opus
claude /model          # 交互式选择模型
```

---

### effortLevel

控制 AI 的努力级别，影响思考深度和回答质量。

```json
{
  "effortLevel": "medium"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `effortLevel` | string | `"medium"` | 努力/思考程度 |

**可选值：**

| 值 | 说明 | 适用场景 |
|----|------|----------|
| `"low"` | 低努力，快速响应 | 简单查询、格式化 |
| `"medium"` | 中等努力 | 日常任务（默认） |
| `"high"` | 高努力 | 复杂代码分析、调试 |
| `"xhigh"` | 超高努力（仅 Opus 4.7） | 极复杂问题 |
| `"max"` | 最大努力 | 最深层次思考 |

> 注意：`xhigh` 仅在 Opus 4.7 上可用，其他模型会降级为 `high`。

**运行时切换：**
```bash
claude --effort high
claude /effort        # 交互式滑块选择
```

---

### minimumVersion

指定最低版本要求，低于此版本时 CLI 会提示升级。

```json
{
  "minimumVersion": "2.1.117"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `minimumVersion` | string | 无 | 最低版本号 |

---

### autoUpdatesChannel

控制自动更新渠道。

```json
{
  "autoUpdatesChannel": "stable"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `autoUpdatesChannel` | string | `"stable"` | 更新渠道 |

**可选值：**

| 值 | 说明 |
|----|------|
| `"stable"` | 稳定版（推荐） |
| `"latest"` | 最新版（包含新功能） |
| `"beta"` | 测试版 |

---

### agent

配置默认使用的代理类型。

```json
{
  "agent": "general-purpose"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `agent` | string | 无 | 代理类型名称 |

**内置代理类型：**

| 类型 | 说明 |
|------|------|
| `"general-purpose"` | 通用代理 |
| `"Explore"` | 快速搜索代理（只读） |
| `"Plan"` | 规划代理 |
| `"claude-code-guide"` | Claude Code 帮助代理 |

---

### attribution

配置 Git 提交归属信息。

```json
{
  "attribution": {
    "commit": "",
    "pr": ""
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `commit` | string | `""` | 提交归属标记 |
| `pr` | string | `""` | PR 归属标记 |

---

## 环境变量配置

### env

配置环境变量，用于 API 认证、代理等。

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
    "ANTHROPIC_MODEL": "claude-sonnet-4-6",
    "DISABLE_TELEMETRY": "true"
  }
}
```

**常用环境变量：**

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `ANTHROPIC_BASE_URL` | API 基础 URL（用于代理或第三方服务） |
| `ANTHROPIC_MODEL` | 默认模型 |
| `ANTHROPIC_AUTH_TOKEN` | OAuth 认证令牌 |
| `DISABLE_TELEMETRY` | 禁用遥测数据收集 |
| `DISABLE_AUTOUPDATER` | 禁用自动更新 |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 禁用非必要网络请求 |
| `ENABLE_PROMPT_CACHING_1H` | 启用 1 小时 prompt 缓存 |
| `FORCE_PROMPT_CACHING_5M` | 强制 5 分钟 prompt 缓存 |
| `API_TIMEOUT_MS` | API 请求超时时间（毫秒） |
| `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | 流式响应空闲超时（默认 90s） |

---

## 权限与安全配置

### permissions.defaultMode

设置默认权限模式。

```json
{
  "permissions": {
    "defaultMode": "default"
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `defaultMode` | string | `"default"` | 权限模式 |

**可选值：**

| 值 | 说明 | 适用场景 |
|----|------|----------|
| `"default"` | 默认模式，关键操作需确认 | 日常使用 |
| `"auto"` | 自动模式，AI 自行判断是否执行 | 高信任环境 |
| `"acceptEdits"` | 自动接受编辑操作 | 快速编辑 |
| `"bypassPermissions"` | 绕过所有权限检查 | 完全信任环境 |
| `"dontAsk"` | 不询问，自动拒绝危险操作 | 安全优先 |
| `"plan"` | 规划模式，需确认后执行 | 审慎操作 |

---

### permissions.allow

配置允许规则列表，自动批准特定操作。

```json
{
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(npm *)",
      "Read(**)",
      "Edit(src/**)"
    ]
  }
}
```

**规则语法：**

| 模式 | 说明 |
|------|------|
| `Bash(git *)` | 允许所有 git 命令 |
| `Bash(npm run *)` | 允许 npm run 命令 |
| `Read(**)` | 允许读取所有文件 |
| `Edit(src/**)` | 允许编辑 src 目录下文件 |
| `Write(.claude/**)` | 允许写入 .claude 目录 |
| `Bash(ls:*)` | 允许 ls 命令 |
| `Bash(cat:*)` | 允许 cat 命令 |

**特殊规则：**

| 规则 | 说明 |
|------|------|
| `Bash(safe)` | 自动允许安全命令（ls, cat 等） |
| `Read` | 允许所有读取操作 |
| `Edit` | 允许所有编辑操作 |
| `WebFetch` | 允许网页抓取 |
| `WebSearch` | 允许网页搜索 |

---

### permissions.deny

配置拒绝规则列表，禁止特定操作。

```json
{
  "permissions": {
    "deny": [
      "Bash(rm -rf /)",
      "Bash(sudo *)",
      "Write(/etc/**)"
    ]
  }
}
```

> 注意：拒绝规则优先级高于允许规则，企业管理规则无法被用户覆盖。

---

### permissions.additionalDirectories

添加额外的允许访问目录。

```json
{
  "permissions": {
    "additionalDirectories": [
      "/opt/projects",
      "~/shared"
    ]
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `additionalDirectories` | array | `[]` | 允许访问的额外目录列表 |

---

## 沙箱配置

### sandbox.network

配置网络沙箱，控制网络访问权限。

```json
{
  "sandbox": {
    "network": {
      "allowedDomains": ["api.anthropic.com", "github.com"],
      "deniedDomains": ["internal.company.com"],
      "allowMachLookup": true,
      "httpProxyPort": 8080,
      "enableWeakerNetworkIsolation": false
    }
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `allowedDomains` | array | `["*"]` | 允许访问的域名列表（`"*"` 表示全部） |
| `deniedDomains` | array | `[]` | 禁止访问的域名列表 |
| `allowMachLookup` | boolean | `false` | macOS 上允许 Mach lookup |
| `httpProxyPort` | number | 无 | HTTP 代理端口 |
| `enableWeakerNetworkIsolation` | boolean | `false` | macOS 上允许自定义 MITM 代理的 TLS 验证 |

---

### sandbox.failIfUnavailable

沙箱不可用时的行为。

```json
{
  "sandbox": {
    "failIfUnavailable": true
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `failIfUnavailable` | boolean | `false` | 沙箱不可用时是否报错退出 |

---

### sandbox 文件系统配置

```json
{
  "sandbox": {
    "denyRead": ["~/.ssh/**", "~/.gnupg/**"],
    "allowRead": ["~/projects/**"]
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `denyRead` | array | `[]` | 禁止读取的路径 |
| `allowRead` | array | `[]` | 在 denyRead 区域内允许读取的例外 |

---

## MCP 服务器配置

### mcpServers

配置 MCP（Model Context Protocol）服务器。

```json
{
  "mcpServers": {
    "slack": {
      "type": "http",
      "url": "https://mcp.slack.dev/mcp",
      "headers": {
        "Authorization": "Bearer xxx"
      },
      "alwaysLoad": true,
      "startupTimeout": 5000
    },
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "/path/to/files"],
      "env": {
        "API_KEY": "xxx"
      },
      "alwaysLoad": false
    },
    "custom": {
      "type": "sse",
      "url": "https://example.com/mcp/sse",
      "oauth": {
        "authServerMetadataUrl": "https://auth.example.com/.well-known/oauth-authorization-server"
      }
    }
  }
}
```

**MCP 服务器配置项：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | string | `"stdio"` | 连接类型：`stdio`, `http`, `sse` |
| `url` | string | 无 | HTTP/SSE 服务器的 URL |
| `command` | string | 无 | stdio 服务器的命令 |
| `args` | array | `[]` | 命令参数 |
| `env` | object | `{}` | 服务器环境变量 |
| `headers` | object | `{}` | HTTP 请求头 |
| `alwaysLoad` | boolean | `false` | 工具始终可用（跳过延迟加载） |
| `startupTimeout` | number | `5000` | 启动超时（毫秒） |
| `disabled` | boolean | `false` | 禁用该服务器 |

**OAuth 配置：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `oauth.authServerMetadataUrl` | string | 自定义 OAuth 元数据发现 URL |

---

### allowedMcpServers / deniedMcpServers

控制允许/禁止的 MCP 服务器（企业策略）。

```json
{
  "allowedMcpServers": ["slack", "filesystem"],
  "deniedMcpServers": ["dangerous-tool"]
}
```

---

## 钩子配置

### hooks

配置事件钩子，在特定事件发生时执行自定义脚本。

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash(rm *)",
        "hooks": [
          {
            "type": "command",
            "command": "echo 'Warning: rm command detected'"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit(**)",
        "hooks": [
          {
            "type": "command",
            "command": "npm run lint --fix ${file_path}"
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "type": "command",
        "command": "echo 'Session started'"
      }
    ],
    "Stop": [
      {
        "type": "command",
        "command": "notify-send 'Claude session ended'"
      }
    ]
  }
}
```

**钩子事件类型：**

| 事件 | 触发时机 |
|------|----------|
| `PreToolUse` | 工具调用前 |
| `PostToolUse` | 工具调用后 |
| `PostToolUseFailure` | 工具调用失败后 |
| `SessionStart` | 会话开始时 |
| `Stop` | 会话结束时 |
| `SubagentStop` | 子代理结束时 |
| `UserPromptSubmit` | 用户提交提示时 |
| `PreCompact` | 压缩前 |
| `TaskCreated` | 任务创建时 |
| `WorktreeCreate` | Worktree 创建时 |
| `ConfigChange` | 配置文件变更时 |
| `CwdChanged` | 工作目录变更时 |
| `FileChanged` | 文件变更时 |
| `Notification` | 通知时 |
| `PermissionDenied` | 权限被拒绝时 |

**钩子类型：**

| 类型 | 说明 |
|------|------|
| `command` | 执行 shell 命令 |
| `mcp_tool` | 调用 MCP 工具 |
| `prompt` | 返回提示文本 |

**钩子返回值：**

| 返回 | 说明 |
|------|------|
| `{"decision": "allow"}` | 允许操作 |
| `{"decision": "deny"}` | 拒绝操作 |
| `{"decision": "ask"}` | 询问用户 |
| `{"decision": "defer"}` | 延迟处理 |
| `exit code 2` | 阻止操作 |

---

## UI/显示配置

### theme

配置界面主题。

```json
{
  "theme": "dark"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `theme` | string | `"dark"` | 主题名称 |

**可选值：**

| 值 | 说明 |
|----|------|
| `"dark"` | 深色主题 |
| `"light"` | 浅色主题 |
| `"auto"` | 自动匹配终端深色/浅色模式 |

**自定义主题：**

主题文件存放于 `~/.claude/themes/` 目录，格式为 JSON：

```json
{
  "name": "my-theme",
  "colors": {
    "primary": "#ff6b00",
    "background": "#1a1a1a",
    "text": "#ffffff"
  }
}
```

---

### tui

配置 TUI（Terminal UI）渲染模式。

```json
{
  "tui": "fullscreen"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tui` | string | `"normal"` | 渲染模式 |

**可选值：**

| 值 | 说明 |
|----|------|
| `"normal"` | 普通模式（默认） |
| `"fullscreen"` | 全屏无闪烁模式 |

**切换命令：**
```bash
claude /tui fullscreen    # 切换到全屏
claude /tui normal        # 切换到普通
```

---

### autoScrollEnabled

控制全屏模式下的自动滚动。

```json
{
  "autoScrollEnabled": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `autoScrollEnabled` | boolean | `true` | 是否自动滚动到最新消息 |

---

### showTurnDuration

显示每轮对话的耗时。

```json
{
  "showTurnDuration": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `showTurnDuration` | boolean | `false` | 是否显示回合耗时（如 "Cooked for 1m 6s"） |

---

### showThinkingSummaries

显示 AI 思考摘要。

```json
{
  "showThinkingSummaries": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `showThinkingSummaries` | boolean | `false` | 是否显示思考摘要 |

> 注意：默认为 `false`，设为 `true` 可恢复显示。

---

### verbose

详细输出模式。

```json
{
  "verbose": false
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `verbose` | boolean | `false` | 是否显示详细输出 |

**切换快捷键：** `Ctrl+O`

---

### language

设置语言偏好。

```json
{
  "language": "zh-CN"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `language` | string | `"en"` | 语言代码 |

**支持语言：**

| 代码 | 语言 |
|------|------|
| `"en"` | 英语 |
| `"zh-CN"` | 简体中文 |
| `"zh-TW"` | 繁体中文 |
| `"ja"` | 日语 |
| `"ko"` | 韩语 |
| `"fr"` | 法语 |
| `"de"` | 德语 |
| `"es"` | 西班牙语 |
| `"ru"` | 俄语 |
| `"pl"` | 波兰语 |
| `"tr"` | 土耳其语 |
| `"nl"` | 荷兰语 |
| `"uk"` | 乌克兰语 |
| `"el"` | 希腊语 |
| `"cs"` | 捷克语 |
| `"da"` | 丹麦语 |
| `"sv"` | 瑞典语 |
| `"no"` | 挪威语 |
| `"pt"` | 葡萄牙语 |
| `"it"` | 意大利语 |

---

### spinnerVerbs

自定义 spinner 动词。

```json
{
  "spinnerVerbs": ["处理", "分析", "思考", "生成"]
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `spinnerVerbs` | array | 内置列表 | 加载动画显示的动作动词 |

---

### spinnerTipsOverride

自定义 spinner 提示。

```json
{
  "spinnerTipsOverride": {
    "tips": [
      "按 Ctrl+C 可中断当前操作",
      "使用 /help 查看帮助",
      "按 Ctrl+O 查看详细输出"
    ],
    "excludeDefault": true
  }
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tips` | array | 内置提示 | 自定义提示文字列表 |
| `excludeDefault` | boolean | `false` | 是否排除内置提示 |

---

### reducedMotion

减少动画效果（无障碍支持）。

```json
{
  "reducedMotion": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `reducedMotion` | boolean | `false` | 减少动画和过渡效果 |

---

### editorMode

编辑器输入模式。

```json
{
  "editorMode": "vim"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `editorMode` | string | `"default"` | 输入模式 |

**可选值：**

| 值 | 说明 |
|----|------|
| `"default"` | 默认输入模式 |
| `"vim"` | Vim 模式（支持 hjkl、i/a 插入等） |

---

### voiceEnabled

启用语音输入。

```json
{
  "voiceEnabled": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `voiceEnabled` | boolean | `false` | 是否启用语音输入 |

---

## 插件配置

### enabledPlugins

启用插件。

```json
{
  "enabledPlugins": {
    "gopls-lsp@claude-plugins-official": true,
    "my-custom-plugin": true
  }
}
```

---

### pluginTrustMessage

插件信任警告的自定义消息（企业策略）。

```json
{
  "pluginTrustMessage": "安装此插件前请先获得 IT 部门批准"
}
```

---

### allowedChannelPlugins

允许的通道插件列表（企业策略）。

```json
{
  "allowedChannelPlugins": ["slack-notifier", "discord-bot"]
}
```

---

### blockedMarketplaces / strictKnownMarketplaces

控制插件市场访问（企业策略）。

```json
{
  "blockedMarketplaces": [
    {
      "hostPattern": "untrusted-plugins.com"
    }
  ],
  "strictKnownMarketplaces": true
}
```

---

## 代理配置

### agents

配置自定义代理。

```json
{
  "agents": {
    "code-reviewer": {
      "description": "Reviews code for issues",
      "prompt": "You are a code reviewer. Analyze the code and report issues.",
      "model": "sonnet",
      "tools": ["Bash", "Read", "Edit"],
      "permissionMode": "default"
    }
  }
}
```

**代理配置项：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `description` | string | 代理描述 |
| `prompt` | string | 代理系统提示 |
| `model` | string | 使用的模型 |
| `tools` | array | 可用工具列表 |
| `permissionMode` | string | 权限模式 |
| `mcpServers` | object | MCP 服务器配置 |
| `hooks` | object | 钩子配置 |
| `initialPrompt` | string | 自动提交的首个提示 |

---

## 存储与清理配置

### cleanupPeriodDays

会话历史清理周期。

```json
{
  "cleanupPeriodDays": 30
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `cleanupPeriodDays` | number | `30` | 清理超过 N 天的会话历史 |

> 注意：设为 `0` 会报错（必须大于 0）。

---

### autoMemoryDirectory

自动记忆存储目录。

```json
{
  "autoMemoryDirectory": "~/.claude/custom-memory"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `autoMemoryDirectory` | string | `~/.claude/projects/<project>/memory/` | 自定义记忆存储目录 |

---

### plansDirectory

计划文件存储目录。

```json
{
  "plansDirectory": "~/.claude/custom-plans"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `plansDirectory` | string | `~/.claude/plans/` | 自定义计划文件目录 |

---

## 企业策略配置

### managed-settings.json

企业级策略配置文件，通常位于：

- macOS/Linux: `/etc/claude-code/managed-settings.json`
- Windows: `C:\Program Files\ClaudeCode\managed-settings.json`

也可以使用 `managed-settings.d/` 目录存放多个策略片段文件。

**企业策略配置项：**

| 配置项 | 说明 |
|------|------|
| `permissions.defaultMode` | 强制权限模式 |
| `permissions.deny` | 强制拒绝规则（不可覆盖） |
| `allowedMcpServers` | 允许的 MCP 服务器 |
| `deniedMcpServers` | 禁止的 MCP 服务器 |
| `blockedMarketplaces` | 禁止的插件市场 |
| `strictKnownMarketplaces` | 仅允许已知市场 |
| `allowedChannelPlugins` | 允许的通道插件 |
| `pluginTrustMessage` | 插件信任警告消息 |
| `forceRemoteSettingsRefresh` | 强制刷新远程设置 |
| `wslInheritsWindowsSettings` | WSL 继承 Windows 设置 |
| `feedbackSurveyRate` | 反馈调查采样率 |

---

### wslInheritsWindowsSettings

WSL 继承 Windows 设置。

```json
{
  "wslInheritsWindowsSettings": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `wslInheritsWindowsSettings` | boolean | `false` | WSL 是否继承 Windows 企业策略 |

---

### forceRemoteSettingsRefresh

强制刷新远程设置。

```json
{
  "forceRemoteSettingsRefresh": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `forceRemoteSettingsRefresh` | boolean | `false` | 启动时阻塞直到远程设置刷新完成 |

---

### feedbackSurveyRate

反馈调查采样率。

```json
{
  "feedbackSurveyRate": 0.1
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `feedbackSurveyRate` | number | `0` | 采样率（0-1，0 表示禁用） |

---

## 其他配置

### prUrlTemplate

自定义 PR URL 模板。

```json
{
  "prUrlTemplate": "https://code-review.company.com/pr/{number}"
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `prUrlTemplate` | string | PR 链接模板，`{number}` 替换为 PR 号 |

---

### modelOverrides

模型 ID 映射覆盖。

```json
{
  "modelOverrides": {
    "sonnet": "arn:aws:bedrock:us-east-1:123456789:inference-profile/us.anthropic.claude-sonnet-4-6"
  }
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `modelOverrides` | object | 模型别名到实际 ID 的映射 |

---

### includeGitInstructions

是否包含 Git 操作指令。

```json
{
  "includeGitInstructions": false
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `includeGitInstructions` | boolean | `true` | 是否在系统提示中包含 commit/PR 指令 |

---

### disableSkillShellExecution

禁用技能中的 shell 执行。

```json
{
  "disableSkillShellExecution": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `disableSkillShellExecution` | boolean | `false` | 禁用 slash 命令中的 inline shell 执行 |

---

### disableDeepLinkRegistration

禁用深度链接注册。

```json
{
  "disableDeepLinkRegistration": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `disableDeepLinkRegistration` | boolean | `false` | 禁用 `claude-cli://` 协议处理 |

---

### worktree.sparsePaths

Worktree sparse checkout 路径。

```json
{
  "worktree": {
    "sparsePaths": ["src/", "tests/", "docs/"]
  }
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `sparsePaths` | array | 大型 monorepo 中仅 checkout 指定目录 |

---

### refreshInterval

状态行刷新间隔。

```json
{
  "refreshInterval": 5
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `refreshInterval` | number | `0` | 状态行命令每 N 秒重新运行 |

---

### showClearContextOnPlanAccept

规划模式接受时显示清除上下文选项。

```json
{
  "showClearContextOnPlanAccept": true
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `showClearContextOnPlanAccept` | boolean | `false` | 是否显示该选项 |

---

## 环境变量参考

### 认证相关

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `ANTHROPIC_BASE_URL` | API 基础 URL |
| `ANTHROPIC_MODEL` | 默认模型 |
| `ANTHROPIC_AUTH_TOKEN` | OAuth 认证令牌 |
| `ANTHROPIC_CUSTOM_HEADERS` | 自定义请求头 |

### AWS Bedrock

| 变量 | 说明 |
|------|------|
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock bearer token |
| `ANTHROPIC_BEDROCK_BASE_URL` | Bedrock 基础 URL |
| `ANTHROPIC_BEDROCK_SERVICE_TIER` | Bedrock 服务层级 |

### Google Vertex AI

| 变量 | 说明 |
|------|------|
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP 项目 ID |
| `ANTHROPIC_VERTEX_REGION` | GCP 区域 |

### 网络与代理

| 变量 | 说明 |
|------|------|
| `API_TIMEOUT_MS` | API 请求超时（毫秒） |
| `CLAUDE_STREAM_IDLE_TIMEOUT_MS` | 流式空闲超时（默认 90s） |
| `NO_PROXY` | 不使用代理的域名 |
| `HTTP_PROXY` | HTTP 代理 |
| `HTTPS_PROXY` | HTTPS 代理 |

### 功能控制

| 变量 | 说明 |
|------|------|
| `DISABLE_TELEMETRY` | 禁用遥测 |
| `DISABLE_AUTOUPDATER` | 禁用自动更新 |
| `DISABLE_UPDATES` | 完全禁用更新 |
| `DISABLE_COMPACT` | 禁用压缩 |
| `DISABLE_PROMPT_CACHING` | 禁用 prompt 缓存 |
| `ENABLE_PROMPT_CACHING_1H` | 启用 1 小时缓存 |
| `FORCE_PROMPT_CACHING_5M` | 强制 5 分钟缓存 |

### MCP 相关

| 变量 | 说明 |
|------|------|
| `MCP_CONNECTION_NONBLOCKING` | MCP 非阻塞连接 |
| `CLAUDE_CODE_MCP_SERVER_NAME` | MCP 服务器名称 |
| `CLAUDE_CODE_MCP_SERVER_URL` | MCP 服务器 URL |

### 子代理与隔离

| 变量 | 说明 |
|------|------|
| `CLAUDE_CODE_FORK_SUBAGENT` | 启用 fork 子代理 |
| `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB` | 清理子进程环境变量 |
| `CLAUDE_CODE_SCRIPT_CAPS` | 限制脚本调用次数 |

### 其他

| 变量 | 说明 |
|------|------|
| `CLAUDE_CONFIG_DIR` | 自定义配置目录 |
| `CLAUDE_CODE_HIDE_CWD` | 隐藏工作目录显示 |
| `CLAUDE_CODE_EXTRA_BODY` | API 请求额外 body |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS` | 禁用 Git 指令 |
| `CLAUDE_CODE_PERFORCE_MODE` | Perforce 模式 |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | 禁用非必要网络请求 |
| `CLAUDE_CODE_USE_POWERSHELL_TOOL` | 启用 PowerShell 工具 |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | 启用实验性代理团队 |
| `FORCE_HYPERLINK` | 强制启用超链接 |
| `CLAUDE_CODE_CERT_STORE` | 证书存储来源 |
| `OTEL_LOG_USER_PROMPTS` | OTEL 记录用户提示 |
| `OTEL_LOG_TOOL_DETAILS` | OTEL 记录工具详情 |
| `OTEL_LOG_TOOL_CONTENT` | OTEL 记录工具内容 |

---

## 完整配置示例

```json
{
  "model": "sonnet",
  "effortLevel": "high",
  "minimumVersion": "2.1.117",
  "autoUpdatesChannel": "stable",

  "env": {
    "ANTHROPIC_API_KEY": "sk-ant-...",
    "ENABLE_PROMPT_CACHING_1H": "true"
  },

  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Bash(git *)",
      "Bash(npm *)",
      "Bash(python *)",
      "Read(**)",
      "Edit(src/**)"
    ],
    "deny": [
      "Bash(rm -rf /*)",
      "Bash(sudo rm *)"
    ],
    "additionalDirectories": [
      "~/shared-projects"
    ]
  },

  "sandbox": {
    "network": {
      "allowedDomains": ["api.anthropic.com", "github.com", "*.github.com"],
      "deniedDomains": []
    },
    "failIfUnavailable": false
  },

  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-filesystem", "~/projects"],
      "alwaysLoad": true
    }
  },

  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit(**)",
        "hooks": [
          {
            "type": "command",
            "command": "npm run lint --fix ${file_path}"
          }
        ]
      }
    ]
  },

  "theme": "dark",
  "tui": "normal",
  "autoScrollEnabled": true,
  "showTurnDuration": false,
  "showThinkingSummaries": false,
  "verbose": false,
  "language": "zh-CN",
  "editorMode": "default",

  "spinnerTipsOverride": {
    "tips": [
      "按 Ctrl+C 中断操作",
      "使用 /help 获取帮助"
    ],
    "excludeDefault": true
  },

  "cleanupPeriodDays": 30,
  "includeGitInstructions": true,

  "enabledPlugins": {
    "gopls-lsp@claude-plugins-official": true
  }
}
```

---

## 参考链接

- [Claude Code GitHub](https://github.com/anthropics/claude-code)
- [Claude Code 官方文档](https://docs.anthropic.com/en/docs/claude-code)
- [Anthropic API 文档](https://docs.anthropic.com/en/api)

---

*文档版本：2026-05-07，基于 Claude Code v2.1.126+*