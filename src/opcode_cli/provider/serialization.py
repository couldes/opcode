import json

from opcode_cli.provider.message import Message


def build_anthropic_messages(messages: list[Message]) -> list[dict]:
    """将内部 Message 列表转为 Anthropic Messages API 格式。"""
    chat_messages = [m for m in messages if m.role != "system"]
    converted = [_convert_to_anthropic(m) for m in chat_messages]
    merged: list[dict] = []
    for msg in converted:
        if (
            merged
            and msg.get("role") == "user"
            and isinstance(msg.get("content"), list)
            and msg["content"]
            and msg["content"][0].get("type") == "tool_result"
            and merged[-1].get("role") == "user"
            and isinstance(merged[-1].get("content"), list)
            and merged[-1]["content"]
            and merged[-1]["content"][0].get("type") == "tool_result"
        ):
            merged[-1]["content"].extend(msg["content"])
        else:
            merged.append(msg)
    return merged


def _convert_to_anthropic(m: Message) -> dict:
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


def build_openai_input(messages: list[Message]) -> list[dict]:
    """将内部 Message 列表转为 OpenAI Responses/Chat API 格式。"""
    return [_convert_to_openai(m) for m in messages]


def _convert_to_openai(m: Message) -> dict:
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


def build_chat_completion_messages(messages: list[Message]) -> list[dict]:
    """转为 OpenAI Chat Completions 格式（兼容 vLLM/Ollama 等）。"""
    return [_convert_to_openai(m) for m in messages]


def build_messages(messages: list[Message], protocol: str) -> list[dict]:
    """统一入口，根据 protocol 参数分流。"""
    if protocol == "anthropic":
        return build_anthropic_messages(messages)
    elif protocol == "openai":
        return build_openai_input(messages)
    else:
        raise ValueError(f"unsupported protocol: '{protocol}'")
