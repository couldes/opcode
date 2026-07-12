import json
from collections.abc import AsyncIterator

from opcode_cli.agent.events import (
    TextDelta,
    ThinkingDelta,
    ToolCallInput,
    ToolCallStart,
)
from opcode_cli.provider.base import StreamChunk, ToolCall


class StreamCollector:
    def __init__(self) -> None:
        self._content_parts: list[str] = []
        self._thinking_parts: list[str] = []
        self._tool_calls: list[ToolCall] = []

    async def collect(
        self, stream: AsyncIterator[StreamChunk]
    ) -> "AsyncIterator[TextDelta | ThinkingDelta | ToolCallStart | ToolCallInput]":
        async for chunk in stream:
            if chunk.content:
                self._content_parts.append(chunk.content)
                yield TextDelta(content=chunk.content)

            if chunk.thinking:
                self._thinking_parts.append(chunk.thinking)
                yield ThinkingDelta(content=chunk.thinking)

            if chunk.tool_use is not None:
                tu = chunk.tool_use
                tool_id = tu["id"]
                name = tu["name"]
                yield ToolCallStart(tool_id=tool_id, name=name)
                import json

                input_str = json.dumps(tu["input"], ensure_ascii=False)
                yield ToolCallInput(tool_id=tool_id, input_delta=input_str)
                self._tool_calls.append(
                    ToolCall(id=tool_id, name=name, input=tu["input"])
                )

    @property
    def content(self) -> str:
        return "".join(self._content_parts)

    @property
    def thinking(self) -> str:
        return "".join(self._thinking_parts)

    @property
    def tool_calls(self) -> list[ToolCall]:
        return list(self._tool_calls)
