from collections.abc import Awaitable, Callable

from opcode_cli.provider.base import BaseProvider, Message, StreamChunk


class ChatController:

    def __init__(self, provider: BaseProvider):
        self._provider = provider
        self.messages: list[Message] = []

    async def send(
        self,
        user_input: str,
        on_chunk: Callable[[StreamChunk], Awaitable[None]],
    ) -> None:
        self.messages.append(Message(role="user", content=user_input))

        content_parts: list[str] = []
        thinking_parts: list[str] = []

        try:
            async for chunk in self._provider.achat(self.messages):
                if chunk.content:
                    content_parts.append(chunk.content)
                if chunk.thinking:
                    thinking_parts.append(chunk.thinking)
                await on_chunk(chunk)

            assistant_content = "".join(content_parts)
            assistant_thinking = "".join(thinking_parts) if thinking_parts else None
            self.messages.append(Message(
                role="assistant",
                content=assistant_content,
                thinking=assistant_thinking,
            ))

        except Exception as e:
            error_msg = f"Error: {e}"
            await on_chunk(StreamChunk(content=error_msg, finish_reason="error"))
