import json
import tempfile
from datetime import datetime
from pathlib import Path

from opcode_cli.provider.base import Message
from opcode_cli.session.archiver import SessionArchiver
from opcode_cli.session.index import list_sessions, get_session_meta, session_exists


class TestSessionIndex:
    def test_list_sessions_empty(self):
        d = Path(tempfile.mkdtemp())
        sessions = list_sessions(d)
        assert sessions == []

    def test_list_sessions_sorted(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)

        # 创建 3 个会话文件
        ids = []
        for i in range(3):
            archiver = SessionArchiver(d, SessionArchiver.generate_id())
            archiver.append([Message(role="user", content=f"test {i}")])
            ids.append(archiver._session_id)

        sessions = list_sessions(d, limit=10)
        assert len(sessions) == 3
        # 按创建时间倒序
        for i in range(len(sessions) - 1):
            assert sessions[i].created_at >= sessions[i + 1].created_at

    def test_get_session_meta(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)

        from opcode_cli.provider.base import Message
        archiver = SessionArchiver(d, SessionArchiver.generate_id())
        archiver.append([Message(role="user", content="find this session")])
        archiver.append([Message(role="assistant", content="response")])

        meta = get_session_meta(d, archiver._session_id)
        assert meta is not None
        assert "find this session" in meta.title
        assert meta.message_count == 2

    def test_session_exists(self):
        d = Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)

        archiver = SessionArchiver(d, SessionArchiver.generate_id())
        archiver.append([Message(role="user", content="hi")])

        assert session_exists(d, archiver._session_id) is True
        assert session_exists(d, "00000000-000000-0000") is False
