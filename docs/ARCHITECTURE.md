# Opcode 架构文档

## 当前运行架构

Opcode 是一个 CLI AI 编程助手。当前运行时仍以原有模块路径为主，重构采用兼容层逐步推进，避免一次迁移破坏已有能力。

```text
opcode_cli.main
  -> presentation.cli.entry       # CLI 编排和依赖装配
  -> agent / context / permission # 核心循环、压缩、权限
  -> provider / mcp / tools       # 外部服务和工具适配
  -> tui / commands / team        # 用户交互和应用编排
```

当前各模块职责：

- `agent/`: Agent 循环、事件流、工具批处理
- `context/`: token 估算、offload、摘要和恢复状态
- `permission/`: 9 层权限决策链
- `prompt/`: 系统提示词和计划模式注入
- `commands/`: 命令解析、补全和处理器
- `provider/`: Anthropic/OpenAI 协议适配
- `tools/`: 内置工具和注册表
- `mcp/`: MCP 服务发现和工具适配
- `tui/`: Textual 界面、时间线和权限控件
- `memory/`, `session/`, `team/`, `subagent/`: 持久化和协作能力

## 本轮重构结果

### 入口职责拆分

`main.py` 现在只是兼容性入口，实际装配位于 `presentation/cli/entry.py`。装配顺序是：

```text
配置 -> Provider -> ToolRegistry -> PermissionChecker
     -> ContextManager -> Prompt/Memory -> Agent -> Commands -> TUI
```

`shared/di/container.py` 提供轻量级构造函数注入容器，支持单例、缺失依赖错误和循环依赖检测。

### 工具实现整合

`tools/file_ops.py` 和 `tools/search_tools.py` 是工具的唯一实现源：

- `BaseFileSystemTool` 统一路径解析和文本读取错误处理
- `BaseSearchTool` 统一搜索根路径解析、跳过目录和遍历逻辑
- `read_file.py`、`write_file.py`、`edit_file.py`、`glob_find.py`、`grep_search.py` 保留为兼容导出
- `infrastructure/tools/` 同样只提供兼容导出，不维护第二份实现

## Pi 机制参考

### ContextManager

保留现有成熟实现：

- F3：大工具结果先 offload 到磁盘
- F4：超限时生成摘要
- SOFT/HARD 双阈值（13K/3K safety margin）
- CircuitBreaker 防止连续压缩失败
- RecoveryState 保留恢复所需上下文

代码位置：`src/opcode_cli/context/manager.py`。

### PermissionChecker

保留现有 9 层决策链：

1. Plan mode
2. Read-only 工具
3. 危险命令黑名单
4. 路径沙盒
5. Session/Base 规则
6. Session allow set
7. Mode fallback
8. 人工确认（由 Agent/TUI 完成）

代码位置：`src/opcode_cli/permission/checker.py`。

### Textual TUI

保留现有 Textual 8.x 约束：

- 使用 `_on_key`，不在其中重复调用父类处理
- Agent 事件由 `TimelineRenderer` 渲染
- 权限等待通过输入控件的 pending state 交互
- `VerticalScroll`、`StatusBar`、`OpcodeChatInput` 维持清晰边界

代码位置：`src/opcode_cli/tui/`。

## 数据流

```text
User Input -> Commands/TUI -> Agent -> PermissionChecker -> ToolRegistry
     ^                                                   |
     +---------------- Event Stream / Timeline <----------+
```

每次 Provider 请求前，Agent 调用 ContextManager；工具执行前，Agent 调用 PermissionChecker。这样压缩和权限机制不会散落在 UI 或具体工具里。

## 后续迁移原则

后续如果继续移动模块，应遵守：

1. 先保留旧路径兼容导出，再切换内部调用方。
2. 每次只迁移一个边界，迁移后运行完整测试集。
3. 不复制核心实现；新路径只能转发到唯一实现或完成真实迁移。
4. ContextManager、PermissionChecker、TUI 先保持行为不变，以测试覆盖为先。

详细的长期计划见 `refactoring_plan.md`。
