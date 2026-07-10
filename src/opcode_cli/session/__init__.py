from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class SessionMeta:
    id: str
    path: Path
    title: str
    message_count: int
    created_at: datetime
    last_message_at: datetime | None = None


@dataclass
class RecoveryResult:
    messages: list
    warnings: list[str]
    time_gap: bool = False


__all__ = ["SessionMeta", "RecoveryResult"]
