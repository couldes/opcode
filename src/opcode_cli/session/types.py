from dataclasses import dataclass
from enum import Enum


class RecordType(Enum):
    SYSTEM_PROMPT = "system_prompt"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL_RESULT = "tool_result"
    COMPRESSION = "compression"
    COMPACT_BOUNDARY = "compact_boundary"


@dataclass
class SessionRecord:
    type: RecordType
    content: dict
    timestamp: float
