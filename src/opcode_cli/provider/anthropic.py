import json
from collections.abc import AsyncIterator

import httpx

from opcode_cli.config import ProviderConfig
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk


class AnthropicProvider(BaseProvider):
    ANTHROPIC_VERSION = "2023-06-01"
    DEFAULT_THINKING_BUDGET = 4000

    def __init__(self, config: ProviderConfig, thinking_budget: int | None = None):
        self._model = config.model
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key
        self._thinking_budget = thinking_budget or self.DEFAULT_THINKING_BUDGET
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    def chat(self, messages: list[Message]) -> Message:
        raise NotImplementedError("use achat() for streaming")

    async def achat(self, messages: list[Message]) -> AsyncIterator[StreamChunk]:
        system_messages = [m for m in messages if m.role == "system"]
        chat_messages = [m for m in messages if m.role != "system"]

        body: dict = {
            "model": self._model,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in chat_messages
            ],
            "stream": True,
            "thinking": {
                "type": "enabled",
                "budget_tokens": self._thinking_budget,
            },
        }
        if system_messages:
            body["system"] = "\n".join(m.content for m in system_messages)

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        async with self._client.stream(
            "POST",
            f"{self._base_url}/v1/messages",
            json=body,
            headers=headers,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise RuntimeError(
                    f"Anthropic API error {response.status_code}: {error_text.decode()}"
                )

            current_block_type: str | None = None

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                data_str = line[len("data: "):]
                if data_str == "[DONE]":
                    break

                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type", "")

                if event_type == "content_block_start":
                    current_block_type = event.get("content_block", {}).get(
                        "type", "text"
                    )

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    delta_type = delta.get("type", "text")
                    if delta_type == "text_delta":
                        yield StreamChunk(
                            content=delta.get("text", ""),
                        )
                    elif delta_type == "thinking_delta":
                        yield StreamChunk(
                            thinking=delta.get("thinking", ""),
                        )

                elif event_type == "message_delta":
                    finish_reason = event.get("delta", {}).get("stop_reason")
                    yield StreamChunk(finish_reason=finish_reason)

                elif event_type == "message_stop":
                    break
