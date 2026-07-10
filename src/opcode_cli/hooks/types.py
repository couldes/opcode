from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class HookCondition:
    mode: str = "all"  # "all" | "any"
    match: dict[str, str] = field(default_factory=dict)


@dataclass
class HookAction:
    type: str  # "command" | "prompt" | "http" | "agent"
    # command fields
    command: str | None = None
    cwd: str | None = None
    env: dict[str, str] | None = None
    # prompt fields
    content: str | None = None
    position: str = "next_iteration"  # "immediate" | "next_iteration"
    scope: str = "once"  # "once" | "persist"
    # http fields
    url: str | None = None
    method: str = "POST"
    headers: dict[str, str] | None = None
    body: str | None = None
    # agent fields (placeholder)
    prompt: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    max_iterations: int = 5


@dataclass
class HookDefinition:
    name: str
    event: str
    action: HookAction
    condition: HookCondition | None = None
    run_once: bool = False
    background: bool = False
    timeout: float = 30.0


@dataclass
class HookContext:
    event: str
    session_id: str
    project_root: str
    timestamp: float
    data: dict = field(default_factory=dict)


@dataclass
class HookResult:
    hook_name: str
    event: str
    triggered: bool
    executed: bool
    action_type: str
    success: bool
    error: str | None = None
    duration_ms: float = 0.0
    output: str | None = None


@dataclass
class HookFireResult:
    results: list[HookResult] = field(default_factory=list)
    intercept: str | None = None
