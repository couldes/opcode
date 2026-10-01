"""Infrastructure layer for external dependencies.

Wraps third-party services and protocols: MCP adapters, LLM providers,
Tools implementation, Subagent runners, Checkpoints, and Worktree isolation.

Key modules:
- mcp: Protocol adapter for external tool servers
- providers: Anthropic/OpenAI/DeepSeek/Gemini implementations
- tools: Built-in tool definitions (file read/write/edit/run)
- subagent: Background agent execution framework
- checkpoint: Save/restore state mechanism
- worktree: Git-based isolation for subagents
"""
