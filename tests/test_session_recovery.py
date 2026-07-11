import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from opcode_cli.provider.base import Message, ToolCall
from opcode_cli.session.archiver import SessionArchiver
from opcode_cli.session.recovery import recover


class TestSessionRecovery:
    def test_recover_normal_session(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)

        archiver = SessionArchiver(d, "20260101-120000-abcd")
        archiver.append([
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi there"),
        ])

        result = asyncio_run(recover(d, "20260101-120000-abcd"))
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[0].content == "hello"
        assert result.messages[1].role == "assistant"
        assert result.warnings == []
        assert result.time_gap is False

    def test_corrupted_line_skipped(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)

        file_path = d / "20260101-120000-abcd.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"role": "user", "content": "good"}\n')
            f.write('this is not valid json\n')
            f.write('{"role": "assistant", "content": "still good"}\n')

        result = asyncio_run(recover(d, "20260101-120000-abcd"))
        assert len(result.messages) == 2
        assert any("corrupted" in w for w in result.warnings)

    def test_truncated_tool_calls(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)

        file_path = d / "20260101-120000-abcd.jsonl"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write('{"role": "user", "content": "read file"}\n')
            f.write(json.dumps({
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "tc1", "name": "read_file", "input": {"path": "/x"}},
                    {"id": "tc2", "name": "write_file", "input": {"path": "/y", "content": "z"}},
                ],
            }) + "\n")
            # 只有 tc1 有 tool result，tc2 缺失（模拟崩溃截断）
            f.write(json.dumps({
                "role": "tool",
                "content": "file content",
                "tool_call_id": "tc1",
                "name": "read_file",
            }) + "\n")

        result = asyncio_run(recover(d, "20260101-120000-abcd"))
        assert len(result.messages) == 3
        # assistant 消息的 tool_calls 应该只剩 tc1
        assistant_msg = result.messages[1]
        assert assistant_msg.role == "assistant"
        assert len(assistant_msg.tool_calls) == 1
        assert assistant_msg.tool_calls[0].id == "tc1"
        assert any("truncated" in w for w in result.warnings)

    def test_session_not_found(self):
        d = Path(tempfile.mkdtemp())
        result = asyncio_run(recover(d, "20260101-120000-abcd"))
        assert len(result.messages) == 0
        assert any("not found" in w for w in result.warnings)


def asyncio_run(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
