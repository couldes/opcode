from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str
    thinking: str | None = None


@dataclass
class StreamChunk:
    content: str = ""
    thinking: str | None = None
    finish_reason: str | None = None  # "stop" | "length" | None


class BaseProvider(ABC):

    @abstractmethod
    def chat(self, messages: list[Message]) -> Message:
        ...

    @abstractmethod
    async def achat(self, messages: list[Message]) -> AsyncIterator[StreamChunk]:
        ...
