from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MemberInfo:
    """花名册中的成员记录。"""
    name: str
    role_name: str
    working_dir: str
    backend: str = "in-process"
    needs_approval: bool = False
    status: str = "pending"  # pending | active | idle | done | failed


@dataclass
class TeamConfig:
    """团队配置，持久化到 config.json。"""
    name: str
    lead_name: str
    root_dir: Path
    created_at: str = ""
    members: dict[str, MemberInfo] = field(default_factory=dict)


@dataclass
class TeamTask:
    """共享任务列表中的一条任务。"""
    task_id: str = ""
    title: str = ""
    description: str = ""
    status: str = "todo"  # todo | in_progress | done | blocked
    priority: str = "medium"  # low | medium | high | urgent
    assigned_to: str | None = None
    depends_on: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class MailboxMessage:
    """邮箱中的一条消息，JSONL 一行。"""
    msg_id: str = ""
    sender: str = ""
    body: str = ""
    timestamp: str = ""
    is_read: bool = False
    summary: str = ""
    protocol: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class MemberContext:
    """成员上下文快照，用于持久化和恢复。"""
    member_name: str
    messages: list[dict] = field(default_factory=list)
    tracker_summary: dict[str, int] = field(default_factory=dict)
    last_task_id: str | None = None
    serialized_at: str = ""
