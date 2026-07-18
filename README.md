# opcode — CLI AI 编程 agent

多提供商、可扩展、终端原生的 AI 编程 agent。

---

## 技术栈

Python 3.10+ · Textual · httpx · openai SDK · Pydantic v2 · MCP SDK · PyYAML · pytest

---

## 权限引擎 · 8 层决策链

每条工具调用经过 8 层管道逐层裁决：

| 层 | 判断 | 结果 |
|----|------|------|
| L0 | 计划模式激活 | 自动允许 |
| L1 | 只读操作 | 自动允许 |
| L1b | 危险命令黑名单（rm -rf /、curl \| sh、fork bomb 等） | 自动拒绝 |
| L2 | 路径沙箱（项目根目录外） | 自动拒绝 |
| L3 | 规则引擎 fnmatch pattern 匹配 | 按策略 |
| L3b | 会话临时放行（"不再询问"） | 允许 |
| L4 | 权限模式矩阵兜底 | 按模式 |
| L5 | 人工确认（TUI 内联提示） | 用户决策 |

四种模式：`strict`（全拒）→ `default`（读放行，写询问）→ `accept-edits`（仅命令询问）→ `permissive`（全放）

---

## 上下文管理 · F3+F4 双层压缩

每次 API 请求前自动执行，最大化有效上下文。

**Phase 1 Offload** — 大型工具结果写入磁盘 `.opcode/offload/<session>/`，对话中替换为预览。单条 20K / 合计 40K 字符触发。廉价、确定性、不消耗 token。

**Phase 2 Summary** — LLM 生成对话摘要替换早期历史，保留最近 5 轮用户交互完整。断路器 3 次失败后静默降级。

双层动机：Offload 解决"大"（单次结果上万字符），Summary 解决"多"（历史累积）。先做廉价操作再消耗 LLM。双阈值策略（软 13K / 硬 3K margin）防频繁触发。

---

## 团队协作

支持多 Agent 以团队形式协同工作，适用于复杂任务分工。

**基础设施**：
- 团队配置持久化至 `~/.opcode/teams/<name>/`，含 config、roster、runtime、tasks
- JSONL 持久化邮箱，成员间异步消息通信
- 共享任务板，支持任务增删改查
- 审批工作流，关键操作需团队审批

**成员管理**：
- `NameRegistry` 管理成员在线状态和花名册
- 成员进程支持 tmux / iTerm2 / in-process 三种后端
- 协调器模式（Coordinator Mode）：禁用直接文件修改，通过协调器编排

**协作工具**：消息收发（单播/广播）、任务管理、团队创建/衍生、合并触发、成员终止。

---

## 子代理系统

两种委派模式，均通过 Git Worktree 实现文件系统级隔离：

| | Role-based | Fork |
|--|-----------|------|
| 上下文 | 空白对话 + 角色提示 | 继承父会话全部消息 |
| 工具 | 三层过滤（禁止嵌套→白名单→黑名单） | 与父会话一致 |
| 隔离 | Git Worktree 独立目录，完成后合并回主项目，过期自动清理 |
| 用途 | 代码审查、测试、文档 | 需完整上下文的分支任务 |

---

## Agent 循环

1. 轮询子代理结果 & 团队邮箱 → 注入记忆 → 上下文压缩（F3→F4）
2. 构建工具 schema（计划模式只读过滤 / 技能白名单过滤）
3. Provider 流式 LLM 响应，收集 token 用量
4. 工具调用处理：权限检查 → 批处理执行（只读并行/写串行）→ 结果存档
5. 异步触发记忆提取

事件驱动架构：Agent 对外暴露 `AsyncIterator[AgentEvent]`，TUI 消费渲染，UI 与 LLM 编排解耦。

---

## 多 LLM 提供商

统一 `BaseProvider` 抽象，消息模型 `Message(role, content, thinking, tool_calls)` 协议无关。两端序列化层负责转换：

```
ProviderManager → AnthropicProvider (httpx 流式 · 思维预算 · 缓存控制)
                → OpenAIProvider (SDK 流式 · tool_call 缓冲)
```

支持自定义 base_url 接入第三方服务。ProviderManager 惰性加载，按协议缓存实例。

---

## 工具系统

`ToolRegistry` 管理所有工具。内置 7 个：

ReadFile · WriteFile · EditFile · RunCommand · GlobFind · GrepSearch · AgentTool

Pydantic v2 参数模型自动生成 schema + 校验。`ToolBatcher` 根据 `is_read_only` 标记并行（只读）/ 串行（写）执行。MCP 协议和技能系统可在运行时动态追加工具。

---

## MCP 协议

通过 Model Context Protocol 动态发现外部工具。支持 stdio 和 HTTP 两种传输方式。首次 Agent 迭代时延迟连接 MCP 服务器，避免启动开销。工具自动注册到 `{server_name}__{tool_name}` 命名空间，经 `MCPToolAdapter` 适配为标准工具接口。

---

## 技能系统

基于 YAML/Markdown 文件的行为包。按作用域分内建 / 用户 / 项目三级。技能可以声明 tool_whitelist 限制可用工具集，支持 `tools/*.py` 动态导入注册。通过 `InstallSkillTool` 从文件系统安装。

---

## 记忆系统

LLM 驱动的异步记忆持久化。每 N 条消息自动触发提取，LLM 输出结构化操作（创建/更新/删除）。按类型分离存储：用户信息、行为偏好、项目上下文、外部参考。基于查询语义匹配回忆，结果注入系统提示。

---

## 事件挂钩

8 个 Agent 生命周期事件：session_start、user_input、iteration_start/end、assistant_response、tool_pre/post_execute、error。支持 4 种动作类型：shell 命令执行、提示注入、子代理派生、HTTP 请求。条件匹配过滤，支持 run_once、background/foreground、超时配置。

---

## 系统提示 · 模块化构建

| 优先级 | 模块 | 来源 |
|--------|------|------|
| 0 | 项目指令 | CLAUDE.md |
| 1-7 | 身份、约束、任务模式、动作执行、工具使用、语气、输出规范 | 固定模块 |
| 90 | 技能索引 | 动态构建 |
| 99 | 记忆上下文 | 系统自动维护 |

支持 Anthropic 缓存控制标记。

---

## 会话管理

JSONL 格式持久化会话存档，支持通过摘要边界恢复历史对话。自动清理过期会话（TTL 可配置）。会话索引支持按日期浏览和选择恢复。

---

## TUI

基于 Textual 的终端界面。`TimelineRenderer` 消费 Agent 事件流，实时创建 TextNode / ThinkingNode / ToolCallNode 等 widget。`PermissionWidget` 提供内联权限提示（y/s/d/n 键盘操作）。`StatusBar` 显示模式和 token 用量。`OpcodeChatInput` 支持多行输入、输入历史持久化、`@` 文件引用展开。
