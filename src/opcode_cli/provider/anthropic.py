import json
from collections.abc import AsyncIterator

import httpx

from opcode_cli.config import ProviderConfig
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk


CACHE_CONTROL_MARKER = "<!-- cache_control: ephemeral -->"


class AnthropicProvider(BaseProvider):
    ANTHROPIC_VERSION = "2023-06-01"
    DEFAULT_THINKING_BUDGET = 4000

    def __init__(self, config: ProviderConfig, thinking_budget: int | None = None):
        self._model = config.model
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key
        self._thinking_budget = thinking_budget or self.DEFAULT_THINKING_BUDGET
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        self._last_usage: dict | None = None

    @property
    def last_usage(self) -> dict | None:
        return self._last_usage

    def chat(self, messages: list[Message]) -> Message:
        raise NotImplementedError("use achat() for streaming")

    async def achat(
        self, messages: list[Message], tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        system_text: str | None = system
        if system_text is None:
            system_msgs = [m for m in messages if m.role == "system"]
            if system_msgs:
                system_text = "\n".join(m.content for m in system_msgs)

        chat_messages = [m for m in messages if m.role != "system"]

        body: dict = {
            "model": self._model,
            "messages": [self._convert_message(m) for m in chat_messages],
            "stream": True,
            "thinking": {
                "type": "enabled",
                "budget_tokens": self._thinking_budget,
            },
        }
        if system_text:
            if CACHE_CONTROL_MARKER in system_text:
                clean_text = system_text.replace(CACHE_CONTROL_MARKER, "").strip()
                body["system"] = [
                    {
                        "type": "text",
                        "text": clean_text,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                body["system"] = system_text
        if tools:
            body["tools"] = tools

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

            tool_use_buf: dict | None = None

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

                if event_type == "message_start":
                    msg = event.get("message", {})
                    usage = msg.get("usage")
                    if usage:
                        self._last_usage = dict(usage)

                elif event_type == "content_block_start":
                    block = event.get("content_block", {})
                    block_type = block.get("type", "")
                    if block_type == "tool_use":
                        tool_use_buf = {
                            "id": block.get("id", ""),
                            "name": block.get("name", ""),
                            "fragments": [],
                        }
                    else:
                        tool_use_buf = None

                elif event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    delta_type = delta.get("type", "text")
                    if delta_type == "text_delta":
                        yield StreamChunk(content=delta.get("text", ""))
                    elif delta_type == "thinking_delta":
                        yield StreamChunk(thinking=delta.get("thinking", ""))
                    elif delta_type == "input_json_delta":
                        if tool_use_buf is not None:
                            tool_use_buf["fragments"].append(
                                delta.get("partial_json", "")
                            )

                elif event_type == "content_block_stop":
                    if tool_use_buf is not None:
                        try:
                            input_dict = json.loads(
                                "".join(tool_use_buf["fragments"])
                            )
                        except json.JSONDecodeError:
                            input_dict = {}
                        yield StreamChunk(
                            tool_use={
                                "id": tool_use_buf["id"],
                                "name": tool_use_buf["name"],
                                "input": input_dict,
                            }
                        )
                        tool_use_buf = None

                elif event_type == "message_delta":
                    finish_reason = event.get("delta", {}).get("stop_reason")
                    yield StreamChunk(finish_reason=finish_reason)

                elif event_type == "message_stop":
                    break

    def _convert_message(self, m: Message) -> dict:
        if m.role == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }
                ],
            }

        if m.tool_calls:
            blocks: list[dict] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append({
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.input,
                })
            return {"role": "assistant", "content": blocks}

        return {"role": m.role, "content": m.content}
