from dataclasses import dataclass


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    thinking: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None
    compressed: bool = False      # 此消息是对话摘要
    offloaded: bool = False       # 此消息内容已存盘


@dataclass
class StreamChunk:
    content: str = ""
    thinking: str | None = None
    finish_reason: str | None = None
    tool_use: dict | None = None
