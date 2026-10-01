# opcode — CLI AI 编程助手

基于终端的 AI 编程助手，支持多 LLM 提供商、8 层权限控制、智能上下文管理和 MCP 协议扩展。

---

## 快速开始

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
opcode
```

---

## 核心架构

```
src/opcode_cli/
├── agent/       # 事件驱动 Agent 循环 (AsyncIterator[AgentEvent])
├── context/     # 双层压缩：offload→summary
├── mcp/         # Model Context Protocol 动态工具发现
├── permission/  # 8 层决策链（L0-L5）
├── provider/    # Anthropic/OpenAI 抽象与流式响应
├── prompt/      # 模块化系统提示词构建
├── tools/       # 内置工具 + MCP 适配器
└── tui/         # Textual 界面，消费 Agent 事件流渲染
```

---

## 核心机制

### 权限引擎 · 8 层决策链

每条工具调用经过 8 层管道逐层裁决：

| 层级 | 判断条件 | 结果 |
|------|----------|------|
| L0 | 计划模式激活 | 自动允许 |
| L1 | 只读操作 | 自动允许 |
| L1b | 危险命令黑名单（`rm -rf /`、`curl \| sh`等） | 自动拒绝 |
| L2 | 路径沙箱（项目根目录外） | 自动拒绝 |
| L3 | 规则引擎（fnmatch pattern 匹配） | 按策略 |
| L3b | 会话临时放行（"不再询问"） | 允许 |
| L4 | 权限模式矩阵兜底 | 按模式 |
| L5 | 人工确认（TUI 内联提示） | 用户决策 |

**四种模式**：`strict`（全拒）→ `default`（读放行，写询问）→ `accept-edits`（仅命令询问）→ `permissive`（全放）

---

### 上下文管理 · F3+F4 双层压缩

每次 API 请求前自动执行，最大化有效上下文。

**Phase 1 Offload**（第 3 层）— 大型工具结果写入磁盘 `.opcode/offload/<session>/`，对话中替换为预览链接。单条 ≥20K 或合计 ≥40K 字符触发。廉价、确定性、不消耗 token。

**Phase 2 Summary**（第 4 层）— LLM 生成对话摘要替换早期历史，保留最近 5 轮用户交互完整。断路器 3 次失败后静默降级。

**双阈值策略**：软阈值 13K / 硬 margin 3K 防频繁触发。**Offload 解决"大"**（单次结果上万字符），**Summary 解决"多"**（历史累积）。先做廉价操作再消耗 LLM。

---

### 动态工具系统

- **内置工具**（7 个，Pydantic v2 参数模型）:
  - ReadFile · WriteFile · EditFile
  - RunCommand
  - GlobFind · GrepSearch
  - AgentTool

- **MCP 集成** — 首次 Agent 迭代时自动 discovery 外部工具，支持 stdio/HTTP 传输。命名空间 `{server_name}__{tool_name}`，经 `MCPToolAdapter` 适配为标准接口。

- **批处理执行** — `ToolBatcher` 根据 `is_read_only` 并行（只读）/ 串行（写）执行。

- **过滤机制** — 角色/技能白名单、嵌套禁止、黑名单三层过滤。

---

## 团队协作

- **持久化配置**：`~/.opcode/teams/<name>/` → config, roster, runtime, tasks
- **消息邮箱**：JSONL 格式持久化，成员异步通信
- **共享任务板**：增删改查、审批工作流
- **进程后端**：tmux / iTerm2 / in-process 三种模式
- **协调器模式**：禁用直接文件修改，通过协调器编排

---

## 子代理模式

两种委派模式，均通过 Git Worktree 实现文件系统级隔离：

| 模式 | 上下文范围 | 工具集 | 适用场景 |
|------|------------|--------|----------|
| Role-based | 空白对话 + 角色提示 | 三层过滤（禁嵌套→白名单→黑名单） | 代码审查、测试、文档 |
| Fork | 继承父会话全部消息 | 与父会话一致 | 需完整上下文的分支任务 |

Git Worktree 独立目录，完成后合并回主项目，过期自动清理。

---

## 事件钩子系统

**8 个生命周期事件**：session_start、user_input、iteration_start/end、assistant_response、tool_pre/post_execute、error

**4 种动作类型**：shell 命令执行、提示注入、子代理派生、HTTP 请求

**配置选项**：条件匹配、run_once、background/foreground、超时配置

**配置文件**：`.opcode/hooks.yaml`

---

## 多 LLM 提供商

统一 `BaseProvider` 抽象，消息模型 `Message(role, content, thinking, tool_calls)` 协议无关。

```
ProviderManager（惰性加载 + 缓存）
├── AnthropicProvider（流式、思维预算、缓存控制标记）
└── OpenAIProvider（SDK 流式、tool_call 缓冲）
```

支持自定义 base_url 接入第三方服务。

---

## TUI 功能特性

- **时间线渲染**：消费 Agent 事件流，实时创建 TimelineWidget
- **权限交互**：内联提示（y/s/d/n 键盘操作）
- **状态栏**：显示模式和 token 用量
- **输入框**：多行输入、历史持久化、`@file` 展开引用

---

## 系统提示词 · 优先级构建

| 优先级 | 模块 | 来源 |
|--------|------|------|
| 0 | 项目指令 | CLAUDE.md |
| 1-7 | 身份、约束、任务模式、动作执行、工具使用、语气、输出规范 | 固定模块 |
| 90 | 技能索引 | 动态构建 |
| 99 | 记忆上下文 | 系统自动维护 |

支持 Anthropic 缓存控制标记。

---

## Textual 8.x 踩坑指南

- 按键处理方法：`_on_key()`（不是 `on_key()`）
- 事件传播终止：`event.stop()`
- Widget 内部 `_on_key` + 自身 BINDINGS > App 层 BINDINGS
- App 层绑定只处理子 widget 未消费的键
- 覆盖 Widget 内建行为应通过子类化而非在 App 层处理

**快速检查 API**:
```bash
python -c "from textual.app import App; print(hasattr(App, 'method_name'))"
python -c "from textual.widgets import Button; [print(b.key, b.action) for b in Button.BINDINGS]"
```

---

## 经验记录

`experience/` 目录记录了本项目开发中踩过的坑和成功的解决方案。遇到类似问题时先查阅，解决新问题后追加新记录。每条记录包含：问题描述 → 根因 → 试错过程 → 成功方法 → 教训。

---

## 技术栈

Python 3.10+ · Textual 8.2.8 · httpx · openai SDK · Pydantic v2 · MCP SDK · PyYAML · pytest

**注意**：Textual 大版本间 API 不兼容，升级前先 `import textual; print(textual.__version__)` 检查。

---

详细开发文档请参考 [CLAUDE.md](CLAUDE.md)。
