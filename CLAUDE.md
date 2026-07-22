# CLAUDE.md

## 项目概要

opcode 是一个 CLI AI 编程助手，通过 Textual TUI 提供交互界面，支持多 LLM 提供商、权限检查、MCP 协议扩展和上下文管理。

## 技术栈

- **Python**: >= 3.10，虚拟环境 `.venv`
- **TUI**: Textual 8.2.8（注意大版本间 API 不兼容，改之前先 `import textual; print(textual.__version__)`）
- **安装**: `.venv/Scripts/pip install -e .`
- **启动**: `opcode` → `opcode_cli.main:main`

## 目录结构

```
src/opcode_cli/
  agent/       — Agent 循环、事件系统、工具调度
  context/     — 上下文管理（Token 估算、大结果存盘、对话摘要）
  mcp/         — MCP 服务发现与工具适配
  permission/  — 权限规则检查
  provider/    — LLM 提供商适配（Anthropic / OpenAI 协议）
  prompt/      — 系统提示词构建
  tools/       — 内置工具实现
  tui/         — Textual TUI（主界面 app.py）
```

## 核心架构

- **Agent** 持有 provider、registry、permission_checker、context_manager，对外暴露 `run(user_input)` 异步生成器
- **ContextManager** 在每次 API 请求前执行 offload（大工具结果存盘）→ summary（对话摘要）两阶段压缩
- **TUI** 通过 `OpcodeApp(agent)` 启动，监听 Agent 事件流渲染 UI
- **工具注册** 在 `main()` 中完成，MCP 工具在 Agent 首次迭代时动态注册
- **权限检查** 支持 strict/default/accept-edits/permissive 四档模式

## Textual 项目参考

- Textual 8.x 中按键处理方法是 `_on_key`（不是 `on_key`）
- 事件传播用 `event.stop()` 终止，`event.prevent_default()` 用法因版本而异
- Widget 内部 `_on_key` 和自身 BINDINGS 优先于 App BINDINGS；App 层绑定只处理子 widget 未消费的键
- 覆盖 widget 内建行为应通过子类化而非在 App 层处理
- 快速检查 API 是否存在：`python -c "from textual.app import App; print(hasattr(App, 'method_name'))"`
- 快速检查 widget BINDINGS：`python -c "from textual.widgets import <Widget>; [print(b.key, b.action) for b in Widget.BINDINGS]"`

## 经验记录

`experience/` 目录记录了本项目开发中踩过的坑和成功的解决方案。遇到类似问题时先查阅，解决新问题后追加新记录。每条记录包含：问题描述 → 根因 → 试错过程 → 成功方法 → 教训。

## 上下文管理阈值

- OffloadManager 单条阈值 20000 字符、合计阈值 40000 字符
- before_request 自动压缩 safety_margin=13000，手动 /compress 时 safety_margin=3000
- ContextManager 依赖 provider 调用 LLM 生成摘要，无 provider 时只做 offload 不做 summary


- OffloadManager 单条阈值 20000 字符、合计阈值 40000 字符
- before_request 自动压缩 safety_margin=13000，手动 /compress 时 safety_margin=3000
- ContextManager 依赖 provider 调用 LLM 生成摘要，无 provider 时只做 offload 不做 summary
