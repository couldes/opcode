from __future__ import annotations

import asyncio
from dataclasses import dataclass

from opcode_cli.tools.base import ToolResult


# --- Spec-compatible event types (frozen dataclass + union) ---

@dataclass(frozen=True)
class StreamText:
    content: str

@dataclass(frozen=True)
class ThinkingText:
    content: str

@dataclass(frozen=True)
class ToolCallStart:
    tool_id: str
    name: str

@dataclass(frozen=True)
class ToolCallInput:
    tool_id: str
    input_delta: str

@dataclass(frozen=True)
class ToolResultEvent:
    tool_id: str
    name: str
    result: ToolResult

@dataclass(frozen=True)
class TokenUsageEvent:
    input_tokens: int
    output_tokens: int

@dataclass(frozen=True)
class ProgressEvent:
    iteration: int
    max_iterations: int

@dataclass(frozen=True)
class DoneEvent:
    finish_reason: str
    content: str = ""

@dataclass(frozen=True)
class ErrorEvent:
    message: str

@dataclass(frozen=True)
class CacheMetricsEvent:
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    input_tokens: int

@dataclass(frozen=True)
class PermissionPromptEvent:
    tool_name: str
    description: str
    future: asyncio.Future = None  # type: ignore

@dataclass(frozen=True)
class OffloadEvent:
    count: int

@dataclass(frozen=True)
class SummarizeEvent:
    summarized_count: int
    total_before: int
    total_after: int

@dataclass(frozen=True)
class CompressionSkippedEvent:
    reason: str

@dataclass(frozen=True)
class SubAgentResultEvent:
    task_id: str
    agent_name: str
    success: bool
    output: str
    input_tokens: int
    output_tokens: int
    error: str | None = None

@dataclass(frozen=True)
class TeamApprovalEvent:
    msg_id: str
    sender: str
    plan_summary: str
    task_ids: list


# --- Aliases for backward compatibility ---
TextDelta = StreamText
ThinkingDelta = ThinkingText


AgentEvent = (
    StreamText
    | ThinkingText
    | ToolCallStart
    | ToolCallInput
    | ToolResultEvent
    | TokenUsageEvent
    | ProgressEvent
    | DoneEvent
    | ErrorEvent
    | CacheMetricsEvent
    | PermissionPromptEvent
    | OffloadEvent
    | SummarizeEvent
    | CompressionSkippedEvent
    | SubAgentResultEvent
    | TeamApprovalEvent
)
