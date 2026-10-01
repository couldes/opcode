import json
import tempfile
from pathlib import Path

from opcode_cli.provider.base import Message
from opcode_cli.session.archiver import SessionArchiver


class TestSessionArchiver:
    def test_generate_id_format(self):
        sid = SessionArchiver.generate_id()
        assert len(sid) == 24  # YYYYMMDD-HHMMSS-xxxxxxxx (32-bit suffix)
        assert sid[8] == "-"
        assert sid[15] == "-"

    def test_generate_id_unique(self):
        ids = {SessionArchiver.generate_id() for _ in range(100)}
        assert len(ids) == 100

    def test_append_and_read(self):
        d = Path(tempfile.mkdtemp())
        archiver = SessionArchiver(d, "20260101-120000-abcd")

        msgs = [
            Message(role="user", content="hello"),
            Message(role="assistant", content="hi there"),
        ]
        archiver.append(msgs)

        rows = archiver.read()
        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "hello"
        assert rows[1]["role"] == "assistant"
        assert rows[1]["content"] == "hi there"

    def test_write_full_overwrites(self):
        d = Path(tempfile.mkdtemp())
        archiver = SessionArchiver(d, "20260101-120000-abcd")

        archiver.append([Message(role="user", content="old")])
        archiver.write_full([Message(role="user", content="new")])

        rows = archiver.read()
        assert len(rows) == 1
        assert rows[0]["content"] == "new"

    def test_read_empty_session(self):
        d = Path(tempfile.mkdtemp())
        archiver = SessionArchiver(d, "20260101-120000-abcd")
        assert archiver.read() == []

    def test_preserves_compressed_offloaded_flags(self):
        d = Path(tempfile.mkdtemp())
        archiver = SessionArchiver(d, "20260101-120000-abcd")

        msg = Message(role="assistant", content="summary", compressed=True, offloaded=True)
        archiver.append([msg])

        rows = archiver.read()
        assert rows[0]["compressed"] is True
        assert rows[0]["offloaded"] is True

    def test_serializes_tool_calls(self):
        d = Path(tempfile.mkdtemp())
        archiver = SessionArchiver(d, "20260101-120000-abcd")

        from opcode_cli.provider.base import ToolCall
        msg = Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="tc1", name="read_file", input={"path": "/x"})],
        )
        archiver.append([msg])

        rows = archiver.read()
        assert rows[0]["tool_calls"] == [
            {"id": "tc1", "name": "read_file", "input": {"path": "/x"}}
        ]
