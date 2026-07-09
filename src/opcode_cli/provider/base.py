from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
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
    finish_reason: str | None = None  # "stop" | "length" | "tool_calls" | "error"
    tool_use: dict | None = None      # {"id": ..., "name": ..., "input": {...}}


class BaseProvider(ABC):

    @abstractmethod
    def chat(self, messages: list[Message]) -> Message:
        ...

    @abstractmethod
    async def achat(
        self, messages: list[Message], tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        ...
