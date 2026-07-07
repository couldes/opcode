import json
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

    async def achat(
        self, messages: list[Message], tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        openai_messages: list[dict] = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        openai_messages.extend(self._convert_message(m) for m in messages)

        kwargs: dict = {
            "model": self._model,
            "messages": openai_messages,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = await self._client.chat.completions.create(**kwargs)

        tool_call_bufs: dict[int, dict] = {}

        async for chunk in stream:
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

    def _convert_message(self, m: Message) -> dict:
        if m.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": m.tool_call_id,
                "content": m.content,
            }

        if m.tool_calls:
            return {
                "role": "assistant",
                "content": m.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.input),
                        },
                    }
                    for tc in m.tool_calls
                ],
            }

        return {"role": m.role, "content": m.content}
