# opcode - CLI AI 编程助手

Opcode 是一个基于终端的 AI 编程助手，支持多 LLM 提供商、工具调用、上下文压缩、权限控制、MCP 扩展和 Textual TUI。

当前版本优先保持既有 CLI 参数、配置格式和核心行为兼容。上下文压缩、权限检查和 TUI 已经是稳定机制，本轮重构主要收敛 CLI 装配、依赖注入和工具实现边界。

## 快速开始

要求：Python 3.10 或更高版本。

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

python -m pip install -e .
```

创建当前目录下的 `opcode.yaml`，或创建 `~/.opcode.yaml`：

```yaml
default: openai-compatible
mode: default

providers:
  - name: openai-compatible
    protocol: openai
    model: your-model-name
    base_url: https://api.example.com/v1
    api_key: replace-with-your-api-key
```

`opcode.yaml` 已被 `.gitignore` 忽略。请不要把 API key 提交到仓库。

启动：

```bash
opcode
opcode --help
```

也可以直接运行模块入口：

```bash
python -m opcode_cli.main
```

## CLI 用法

```text
opcode [-h] [-c CONFIG] [-p PROVIDER]
       [--max-iterations MAX_ITERATIONS]
       [--mode {strict,default,accept-edits,permissive}]
       [--team TEAM] [--member MEMBER]
       [--backend {auto,tmux,iterm2,in-process}]
```

常用参数：

| 参数 | 说明 |
|------|------|
| `-c`, `--config` | 指定 YAML 配置文件；默认查找 `./opcode.yaml` 和 `~/.opcode.yaml` |
| `-p`, `--provider` | 选择配置中的 provider |
| `--max-iterations` | 每轮最多执行的工具调用迭代次数，默认 `25` |
| `--mode` | 权限模式：`strict`、`default`、`accept-edits`、`permissive` |
| `--team`、`--member` | 以团队成员模式启动 |
| `--backend` | 团队成员后端：`auto`、`tmux`、`iterm2`、`in-process` |

评测命令：

```bash
opcode eval <test-case-or-directory> [--output <path>]
opcode eval-report <results-directory> [--output <path>]
```

## 权限模式

工具调用经过 `PermissionChecker` 的 9 层决策链：计划模式、只读工具、危险命令黑名单、操作系统沙盒预留检查、路径沙盒、规则引擎、会话临时放行、权限模式兜底和人工确认。

| 模式 | 行为 |
|------|------|
| `strict` | 默认拒绝，需要显式放行 |
| `default` | 只读操作自动放行，写操作询问 |
| `accept-edits` | 接受文件编辑，命令执行仍需询问 |
| `permissive` | 尽量自动放行 |

危险命令和项目根目录外的文件访问会在进入普通权限兜底前被拦截。人工确认由 Agent 和 TUI 协作完成。

## 上下文管理

每次调用 Provider 前，`ContextManager` 会按需执行两阶段压缩：

1. **Offload**：大型工具结果写入 `.opcode/offload/<session>/`，对话中保留预览和文件引用。
2. **Summary**：历史上下文过长时由 LLM 生成摘要，保留最近交互并替换早期历史。

当前实现保留以下保护机制：

- 单条结果和总结果双阈值
- 自动压缩和手动压缩使用不同安全边距
- `CompactCircuitBreaker` 防止连续摘要失败
- `RecoveryState` 支持压缩后的恢复

## 工具系统

内置工具包括文件读写、编辑、命令执行、文件匹配和内容搜索。工具执行由 `ToolRegistry` 统一管理，`ToolBatcher` 对只读操作并行执行，对写操作串行执行。

文件工具和搜索工具的公共路径处理已分别收敛到：

- `src/opcode_cli/tools/file_ops.py`
- `src/opcode_cli/tools/search_tools.py`

原有的 `read_file.py`、`write_file.py`、`edit_file.py`、`glob_find.py` 和 `grep_search.py` 仍保留为兼容导出。`infrastructure/tools/` 只提供兼容转发，不维护第二份实现。

MCP 服务在首次 Agent 迭代时发现并注册，工具名称使用 `{server_name}__{tool_name}` 命名空间。

## 架构概览

当前运行时的依赖装配路径如下：

```text
opcode_cli.main
  -> presentation.cli.entry       CLI 参数解析和应用装配
  -> provider / tools              LLM 和工具注册
  -> permission / context          权限检查和上下文管理
  -> prompt / memory / session     提示词、记忆和会话持久化
  -> agent                         Agent 事件循环
  -> tui / commands                用户界面和命令处理
```

主要目录：

```text
src/opcode_cli/
├── agent/        Agent 循环、事件流和工具批处理
├── commands/     命令解析、补全和处理器
├── context/      token 估算、offload、摘要和恢复
├── hooks/        生命周期事件钩子
├── mcp/          MCP 服务发现和工具适配
├── memory/       项目和用户记忆
├── permission/   权限决策链
├── prompt/       系统提示词和计划模式注入
├── provider/     Anthropic/OpenAI 协议适配
├── session/      会话归档
├── tools/        内置工具和工具注册表
├── tui/          Textual 界面和权限交互
├── presentation/cli/  CLI 组合根
└── shared/       配置兼容层和 DI 容器
```

`main.py` 仍是稳定的兼容入口，实际应用装配位于 `presentation/cli/entry.py`。新目录并不意味着所有旧业务包已经完成迁移；核心模块目前继续使用原有导入路径，以降低兼容风险。

## TUI

标准启动方式进入 Textual TUI，提供：

- Agent 事件时间线实时渲染
- 工具调用和结果展示
- 权限确认交互
- 多行输入和命令处理
- 状态栏和 token 用量显示

项目遵循 Textual 8.x 的事件处理约束：使用 `_on_key()`，通过 `event.stop()` 停止事件传播，并优先在 Widget 层处理按键行为。

团队成员模式的 CLI 参数已经保留，但当前入口仍是轻量兼容实现；完整团队协调流程由 `team/` 和相关基础设施继续演进。

## 开发与测试

安装开发依赖并运行完整测试：

```bash
python -m pip install -e .
python -m pytest tests/ -q --tb=short
```

当前重构阶段验证结果：

```text
557 passed, 1 skipped
```

常用检查：

```bash
python -m compileall -q src tests
python -m opcode_cli.main --help
```

文档入口：

- [重构实施计划](refactoring_plan.md)

## 技术栈

Python 3.10+、Textual、httpx、OpenAI SDK、Pydantic v2、MCP SDK、PyYAML 和 pytest。

Textual 跨大版本存在 API 差异。升级前请先确认实际安装版本，并运行完整测试集。
