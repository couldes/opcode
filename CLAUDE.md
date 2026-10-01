# opcode — Development Guide

## Project Overview

CLI AI coding agent with Textual TUI, multi-provider LLM support, 8-layer permission control, MCP tool discovery, and dual-phase context compression.

## Tech Stack

- **Python**: >= 3.10 (virtualenv `.venv`)
- **TUI**: Textual 8.2.8 (⚠️ API changes across majors; check version before updates)
- **Install**: `python -m pip install -e .`
- **Run**: `opcode` → entry point `opcode_cli.main:main`

## Directory Structure

```
src/opcode_cli/
├── agent/       # Event loop, AsyncIterator[AgentEvent], tool dispatching
├── context/     # Token counting, offload manager, conversation summarization
├── mcp/         # MCP service discovery, tool adaptation (MCPToolAdapter)
├── permission/  # 8-layer decision pipeline (L0-L5), mode matrix
├── provider/    # BaseProvider abstract, Anthropic/OpenAI adapters with streaming
├── prompt/      # Modular system prompt builder, cache control tags
├── tools/       # Pydantic v2 parameter models, ToolRegistry, ToolBatcher
└── tui/         # TimelineRenderer, PermissionWidget, OpcodeApp(agent)
```

## Core Architecture Patterns

### Agent Loop

**AsyncIterator** yielding events consumed by TUI. Each iteration:

1. Poll subagents & team mailbox → inject memories → context compression
2. Build filtered tool schema (role-based / skill-based whitelists)
3. Stream LLM response (track token usage)
4. Execute tools: permission check → batch run (read parallel / write serial) → archive results
5. Trigger async memory extraction

**Events emitted**: session_start, user_input, iteration_start/end, assistant_response, tool_pre/post_execute, error.

### ContextManager · Compression Pipeline

Runs before every API call:

```
offload(≥20K/single, ≥40K/total) → summary(LLM-generated)
   ↓                                    ↓
disk storage                          keep last 5 interactions
replace with preview link             circuit breaker after 3 failures
```

**Thresholds**:
- Auto-compression (before_request): safety_margin=13000
- Manual `/compress`: safety_margin=3000
- No provider? Only offload, no summary.

### PermissionChecker

Eight-layer sequential checks:

| Layer | Check | Result |
|-------|-------|--------|
| L0 | Plan mode | auto_allow |
| L1 | Read-only | auto_allow |
| L1b | Danger blacklist | auto_block |
| L2 | Path sandbox | block outside root |
| L3 | fnmatch rules | policy |
| L3b | Session override | allow |
| L4 | Mode matrix | fallback |
| L5 | Human confirm | user_decision |

**Modes**: `strict`(deny_all) → `default`(read_ok,write_ask) → `accept-edits`(commands_ask) → `permissive`(allow_all)

### Tool Registry

**Built-in** (Pydantic v2 models):
- ReadFile · WriteFile · EditFile
- RunCommand
- GlobFind · GrepSearch
- AgentTool

**Dynamic registration**: MCP tools at first Agent iteration, skills importing `tools/*.py`.

**Execution**: `ToolBatcher` parallelizes read-only (is_read_only=True), serializes writes.

### MCP Integration

Auto-discovers external tools via stdio or HTTP transport. Namespace pattern `{server_name}__{tool_name}`. Adapter layer converts to standard tool interface (`MCPToolAdapter`). Lazy connection on first iteration to avoid startup overhead.

### Team System

**Persistence**: `~/.opcode/teams/<name>/` → config, roster, runtime, tasks

**Features**:
- JSONL message mailbox (async communication)
- Shared task board (CRUD operations)
- Approval workflow for critical ops
- Member backends: tmux / iTerm2 / in-process
- Coordinator mode: disable direct edits, use orchestrator

### Subagent Modes

Git Worktree isolation, auto-cleanup:

| Mode | Context Scope | Tool Filter | Scenario |
|------|---------------|-------------|----------|
| Role-based | Blank + role prompt | forbid nesting → whitelist → blacklist | Review, test, docs |
| Fork | Full parent history | parent's full set | Branch tasks |

## Event Hooks

8 lifecycle points × 4 action types:

**Actions**: shell_command, prompt_injection, spawn_subagent, http_request

**Options**: conditions, run_once flag, background/foreground, timeout

**Config**: `.opcode/hooks.yaml`

## System Prompt · Priority Levels

| Priority | Module | Source |
|----------|--------|--------|
| 0 | Project instructions | CLAUDE.md |
| 1-7 | Identity, constraints, task mode, actions, tools, tone, output | fixed modules |
| 90 | Skill index | dynamic |
| 99 | Memory context | automatic |

Supports Anthropic caching control marks.

## Textual 8.x Gotchas

- Key handler name: `_on_key()` not `on_key()`
- Stop event propagation: `event.stop()`
- Widget-level `_on_key` + own BINDINGS > App-level BINDINGS
- App bindings only handle keys not consumed by children
- Override widget behavior via subclassing, not app-level handlers

**Quick checks**:
```bash
python -c "from textual.app import App; print(hasattr(App, 'method_name'))"
python -c "from textual.widgets import Button; [print(b.key, b.action) for b in Button.BINDINGS]"
```

## Skills System

Behavior packages defined in YAML/Markdown. 3 scopes: built-in / user / project.

**Features**:
- Tool whitelist/blacklist declarations
- Dynamic imports from `tools/*.py`
- Installed via `InstallSkillTool`

## Experience Log

`experience/` directory documents lessons learned during development. Each record contains: Problem → Root Cause → Trial Process → Solution → Lessons.

Reference before tackling similar issues; append new records after resolution.

## Testing

```bash
pytest tests/ -v --tb=short
```

Async mode configured via `pyproject.toml`.

---

## Quick Reference Checklist

- [ ] Check Textual version before API changes
- [ ] Consult `experience/` before re-solving known issues
- [ ] Use `offload` for big results (>20K), `summary` for long conversations
- [ ] Remember safety margins: auto=13K, manual=3K
- [ ] Event hooks config: `.opcode/hooks.yaml`
- [ ] Team persistence: `~/.opcode/teams/<name>/`
- [ ] MCP tools registered at first Agent iteration, not startup
- [ ] Git Worktree = isolated + auto-cleanup for subagents
