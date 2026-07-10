from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class MemoryType(Enum):
    USER = "user"
    FEEDBACK = "feedback"
    PROJECT = "project"
    REFERENCE = "reference"


@dataclass
class MemoryNote:
    name: str
    description: str
    type: MemoryType
    content: str
    file_path: Path
    updated_at: datetime


@dataclass
class MemoryUpdateResult:
    action: str  # "create" | "update" | "delete" | "none"
    name: str
    type: MemoryType | None = None
    description: str | None = None
    content: str | None = None
