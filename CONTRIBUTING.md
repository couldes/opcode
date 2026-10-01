# 开发指南 (Contributing to Opcode)

## Prerequisites

- **Python**: >= 3.10
- **Virtual Environment**: `.venv` (recommended)
- **Git**: For version control

## Quick Start

### 1. Setup Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

### 2. Install Dependencies

```bash
pip install -e .
```

Or manually:

```bash
python -m pip install -e .
python -m pip install mypy==1.8.0 black==24.1.0 isort==5.13.2 pytest==7.4.0
```

### 3. Run Opcode

```bash
opcode
```

Or run the CLI entry point directly:

```bash
python -m opcode_cli.presentation.cli.entry
```

## Development Workflow

### Code Style

We follow PEP 8 with these tools:

```bash
# Format code
black src/opcode_cli tests/

# Sort imports
isort src/opcode_cli tests/

# Type check (strict mode)
mypy --strict src/opcode_cli/

# Lint (flake8)
flake8 src/opcode_cli tests/
```

### Testing

```bash
# Run all tests
pytest tests/ -v --tb=short

# Run specific test file
pytest tests/test_agent.py -v

# Run with coverage
pytest tests/ --cov=src/opcode_cli --cov-report=html
```

### Git Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git commit -m "feat: add support for new LLM provider"
git commit -m "refactor: reorganize core modules structure"
git commit -m "docs: update architecture documentation"
git commit -m "test: add unit tests for context manager"
git commit -m "fix: resolve permission check deadlock issue"
```

## Architecture Overview

See `ARCHITECTURE.md` for detailed layer design and data flow.

Key directories:

- `src/opcode_cli/agent/`, `context/`, `permission/`, `prompt/` - 核心逻辑
- `src/opcode_cli/commands/`, `hooks/`, `session/`, `team/` - 应用编排
- `src/opcode_cli/provider/`, `mcp/`, `tools/`, `subagent/` - 基础设施适配
- `src/opcode_cli/tui/` - Textual 用户界面
- `src/opcode_cli/presentation/cli/` - 新的 CLI 装配入口
- `src/opcode_cli/shared/` - 配置和 DI 等共享能力

## Core Concepts

### Agent Loop

The main event loop that:
1. Polls user input and subagents
2. Builds filtered tool schema
3. Streams LLM response
4. Executes tools (permission → batch run → archive)
5. Triggers async memory extraction

**Event types**: session_start, user_input, iteration_start/end, assistant_response, tool_pre/post_execute, error

### Context Management

Before every API call:
```
offload (≥20K/single, ≥40K/total) → summary(LLM-generated)
   ↓                                    ↓
disk storage                          keep last 5 interactions
replace with preview link             circuit breaker after 3 failures
```

### Permission Checking

9-layer decision chain:
```
Plan Mode → Read-only → Danger Blacklist → Path Sandbox 
→ Rule Engine → Session Allow → Mode Fallback → HITL
```

Mode matrix: strict(default deny) → default(read_ok, write_ask) 
→ accept-edits(commands_ask) → permissive(allow_all)

## Debugging Tips

### Enable Debug Logging

```bash
export OPCL_DEBUG=1
opcode
```

### Profile Performance

```bash
py-spy record -o profile.svg -- python -m opcode_cli --help
```

### Check Tool Schemas

```bash
python -c "from opcode_cli.tools.registry import ToolRegistry; r = ToolRegistry(); print(r.to_anthropic_format())"
```

## Common Issues

### "Module not found" Error

```bash
python -m pip install -e .
```

### Textual Version Mismatch

Check version before updates:
```bash
python -c "import textual; print(textual.__version__)"
```

### Permission Denied When Running Commands

Check your project's `.opcode/rules.yaml` permissions.

## Getting Help

- Check existing issues on GitHub
- Review `experience/` directory for known problems
- Create a new issue with reproduction steps

## Contributing

1. Fork the repository
2. Create a feature branch (`feature/new-tool`)
3. Make your changes
4. Write tests
5. Update documentation
6. Submit a PR

Thank you for contributing! 🙏

---

**Last Updated**: 2025-12-19  
**Version**: v0.2.0-refactor
