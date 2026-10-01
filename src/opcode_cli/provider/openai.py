from collections.abc import AsyncIterator
import json

from openai import AsyncOpenAI

from opcode_cli.config import ProviderConfig
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk
from opcode_cli.provider.serialization import build_openai_input


class OpenAIProvider(BaseProvider):

    def __init__(self, config: ProviderConfig):
        self._model = config.model
        self._client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
        )
        self._last_usage: dict | None = None

    @property
    def last_usage(self) -> dict | None:
        return self._last_usage

    def chat(self, messages: list[Message]) -> Message:
        raise NotImplementedError("use achat() for streaming")

    @staticmethod
    def _normalize_usage(usage) -> dict:
        details = getattr(usage, "prompt_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) or 0
        return {
            "input_tokens": usage.prompt_tokens,
            "output_tokens": usage.completion_tokens,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": cached,
        }

    async def achat(
        self, messages: list[Message], tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        openai_messages: list[dict] = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        openai_messages.extend(build_openai_input(messages))

        kwargs: dict = {
            "model": self._model,
            "messages": openai_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self._client.chat.completions.create(**kwargs)

        tool_call_bufs: dict[int, dict] = {}

        async for chunk in stream:
            if chunk.usage:
                self._last_usage = self._normalize_usage(chunk.usage)

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_bufs:
                        tool_call_bufs[idx] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }
                    buf = tool_call_bufs[idx]
                    if tc.id:
                        buf["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            buf["name"] = tc.function.name
                        if tc.function.arguments:
                            buf["arguments"] += tc.function.arguments

            if delta.content:
                yield StreamChunk(content=delta.content)

            if finish_reason:
                for idx in sorted(tool_call_bufs.keys()):
                    buf = tool_call_bufs[idx]
                    try:
                        input_dict = json.loads(buf["arguments"])
                    except json.JSONDecodeError:
                        input_dict = {}
                    yield StreamChunk(
                        tool_use={
                            "id": buf["id"],
                            "name": buf["name"],
                            "input": input_dict,
                        }
                    )
                yield StreamChunk(finish_reason=finish_reason)

