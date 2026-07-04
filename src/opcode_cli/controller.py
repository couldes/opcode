from collections.abc import Awaitable, Callable

from opcode_cli.provider.anthropic import AnthropicProvider
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk, ToolCall
from opcode_cli.tools.registry import ToolRegistry


class ChatController:

    def __init__(
        self,
        provider: BaseProvider,
        registry: ToolRegistry,
        max_iterations: int = 25,
    ):
        self._provider = provider
        self._registry = registry
        self._max_iterations = max_iterations
        self.messages: list[Message] = []

    async def send(
        self,
        user_input: str,
        on_chunk: Callable[[StreamChunk], Awaitable[None]],
        on_tool_call: Callable[..., Awaitable[None]] | None = None,
    ) -> None:
        self.messages.append(Message(role="user", content=user_input))
        tools = self._build_tools()

        for _ in range(self._max_iterations):
            content_parts: list[str] = []
            thinking_parts: list[str] = []
            tool_use: dict | None = None

            try:
                async for chunk in self._provider.achat(self.messages, tools=tools):
                    if chunk.tool_use is not None:
                        tool_use = chunk.tool_use
                    else:
                        if chunk.content:
                            content_parts.append(chunk.content)
                        if chunk.thinking:
                            thinking_parts.append(chunk.thinking)
                    await on_chunk(chunk)
            except Exception as e:
                await on_chunk(StreamChunk(
                    content=f"Error: {e}", finish_reason="error"
                ))
                return

            if tool_use is None:
                self.messages.append(Message(
                    role="assistant",
                    content="".join(content_parts),
                    thinking="".join(thinking_parts) if thinking_parts else None,
                ))
                return

            tool_id = tool_use["id"]
            tool_name = tool_use["name"]
            tool_input = tool_use["input"]

            self.messages.append(Message(
                role="assistant",
                content="".join(content_parts),
                tool_calls=[ToolCall(id=tool_id, name=tool_name, input=tool_input)],
            ))

            if on_tool_call:
                await on_tool_call(tool_name, tool_input)

            result = await self._registry.execute(tool_name, **tool_input)

            result_content = (
                result.content
                if result.success
                else f"Error: {result.error}"
            )
            self.messages.append(Message(
                role="tool",
                content=result_content,
                tool_call_id=tool_id,
                name=tool_name,
            ))

            if on_tool_call:
                await on_tool_call(tool_name, tool_input, result)

        # max iterations reached
        await on_chunk(StreamChunk(
            content="\n\n[max iterations reached]", finish_reason="stop"
        ))

    def _build_tools(self) -> list[dict] | None:
        if isinstance(self._provider, AnthropicProvider):
            return self._registry.to_anthropic_format()
        return self._registry.to_openai_format()
