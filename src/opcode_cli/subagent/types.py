from dataclasses import dataclass, field


@dataclass
class AgentRole:
    """子 Agent 角色定义，从 Markdown + YAML frontmatter 解析。"""
    name: str
    description: str
    system_prompt: str = ""
    tools: list[str] | None = None
    tools_blacklist: list[str] = field(default_factory=list)
    model: str = "inherit"
    max_turns: int = 10
    permission_mode: str = "inherit"
    source: str = ""


@dataclass
class BackgroundTask:
    """后台子 Agent 任务状态记录。"""
    task_id: str
    agent_name: str
    status: str = "pending"
    started_at: float = 0.0
    finished_at: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    result: str | None = None
    error: str | None = None
    mode: str = "background"
