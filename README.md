# opcode — CLI AI Coding Agent

A terminal-based AI coding assistant with multi-provider LLM support, 8-layer permission control, and intelligent context management.

## Quick Start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
opcode
```

## Core Architecture

```
src/opcode_cli/
├── agent/       # Event-driven agent loop (AsyncIterator[AgentEvent])
├── context/     # Dual-phase compression: offload→summary
├── mcp/         # Model Context Protocol for dynamic tool discovery
├── permission/  # 8-layer decision pipeline (L0-L5)
├── provider/    # Anthropic/OpenAI abstraction with streaming
├── prompt/      # Modular system prompt builder
├── tools/       # Built-in tools + MCP adapters
└── tui/         # Textual-based UI rendering event streams
```

## Key Mechanisms

### Permission Engine · 8-Layer Pipeline

Every tool call passes through 8 consecutive checks:

| Layer | Check | Action |
|-------|-------|--------|
| L0 | Plan mode active | Auto-allow |
| L1 | Read-only operation | Auto-allow |
| L1b | Dangerous command blacklist | Auto-block |
| L2 | Path sandboxing | Auto-block |
| L3 | Rule engine (fnmatch patterns) | Policy-based |
| L3b | Session temporary override | Allow |
| L4 | Permission mode matrix | Fallback |
| L5 | Human confirmation | User decision |

**Modes**: `strict` → `default` → `accept-edits` → `permissive`

### Context Compression · F3+F4 Double Layer

Executed before every API request:

1. **Offload** (Phase 3): Large results (>20K chars/single or >40K total) written to `.opcode/offload/<session>/`, replaced with preview links. Cheap, deterministic.

2. **Summary** (Phase 4): LLM generates conversation summary, keeping last 5 user interactions complete. Circuit breaker after 3 failures.

**Strategy**: Soft threshold 13K / Hard margin 3K to prevent thrashing. Offload handles "big", Summary handles "many".

### Dynamic Tool System

- **Built-in**: ReadFile, WriteFile, EditFile, RunCommand, GlobFind, GrepSearch, AgentTool
- **MCP Integration**: Auto-discovers external tools via stdio/HTTP transport at first iteration
- **Batching**: `ToolBatcher` parallelizes read-only operations, serializes writes
- **Filtering**: Role-based and skill-based whitelists/blacklists

### Team Collaboration

- Multi-agent coordination with shared task board
- JSONL persistent message mailbox
- Member processes: tmux / iTerm2 / in-process backends
- Coordinator mode disables direct edits, uses orchestrator

## Subagent Modes

Both implemented via Git Worktree isolation:

| Mode | Context | Tools | Use Case |
|------|---------|-------|----------|
| Role-based | Blank slate + role prompt | 3-layer filtered | Code review, testing, docs |
| Fork | Inherits full session history | Parent's full set | Branch tasks needing context |

## Event Hooks

8 lifecycle events with 4 action types:

- **Events**: session_start, user_input, iteration_start/end, assistant_response, tool_pre/post_execute, error
- **Actions**: shell execution, prompt injection, subagent spawning, HTTP requests
- **Filters**: run_once, background/foreground, timeout config

## Provider Abstraction

```
ProviderManager (lazy cache)
├── AnthropicProvider (streaming, thinking budget, cache control)
└── OpenAIProvider (SDK streaming, tool_call buffering)
```

Custom base_url supported for third-party services.

## TUI Features

- Real-time timeline rendering from Agent events
- Inline permission prompts (y/s/d/n keys)
- Token usage & mode display
- Multi-line chat input with file expansion (`@file`)

---

See [CLAUDE.md](CLAUDE.md) for implementation details and development setup.
