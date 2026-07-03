from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from opcode_cli.config import ProviderConfig
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk


class OpenAIProvider(BaseProvider):

    def __init__(self, config: ProviderConfig):
        self._model = config.model
        self._client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )

    def chat(self, messages: list[Message]) -> Message:
        raise NotImplementedError("use achat() for streaming")

    async def achat(self, messages: list[Message]) -> AsyncIterator[StreamChunk]:
        openai_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=openai_messages,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta
                finish_reason = chunk.choices[0].finish_reason
                if delta.content:
                    yield StreamChunk(
                        content=delta.content,
                        finish_reason=finish_reason,
                    )
                elif finish_reason:
                    yield StreamChunk(finish_reason=finish_reason)
