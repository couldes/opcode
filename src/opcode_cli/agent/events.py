from dataclasses import dataclass

from opcode_cli.tools.base import ToolResult


@dataclass
class TextDelta:
    content: str


@dataclass
class ThinkingDelta:
    content: str


@dataclass
class ToolCallStart:
    tool_id: str
    name: str


@dataclass
class ToolCallInput:
    tool_id: str
    input_delta: str


@dataclass
class ToolResultEvent:
    tool_id: str
    name: str
    result: ToolResult


@dataclass
class TokenUsageEvent:
    input_tokens: int
    output_tokens: int


@dataclass
class ProgressEvent:
    iteration: int
    max_iterations: int


@dataclass
class DoneEvent:
    finish_reason: str
    content: str = ""


@dataclass
class ErrorEvent:
    message: str


@dataclass
class CacheMetricsEvent:
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    input_tokens: int


@dataclass
class PermissionPromptEvent:
    tool_call_id: str
    tool_name: str
    args_str: str


AgentEvent = (
    TextDelta
    | ThinkingDelta
    | ToolCallStart
    | ToolCallInput
    | ToolResultEvent
    | TokenUsageEvent
    | ProgressEvent
    | DoneEvent
    | ErrorEvent
    | CacheMetricsEvent
    | PermissionPromptEvent
)
