from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from opcode_cli.provider.message import Message, StreamChunk, ToolCall


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
