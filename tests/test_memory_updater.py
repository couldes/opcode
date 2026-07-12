import asyncio
import json
import tempfile
from datetime import datetime
from pathlib import Path

from opcode_cli.memory.index import MemoryIndex
from opcode_cli.memory.store import MemoryStore
from opcode_cli.memory.types import MemoryNote, MemoryType
from opcode_cli.memory.updater import MemoryUpdater, _extract_last_exchange, _parse_update_results
from opcode_cli.provider.base import Message


class TestMemoryUpdater:
    def test_extract_last_exchange(self):
        messages = [
            Message(role="user", content="first question"),
            Message(role="assistant", content="first answer"),
            Message(role="user", content="second question"),
            Message(role="assistant", content="second answer"),
        ]
        exchange = _extract_last_exchange(messages)
        assert "second question" in exchange
        assert "second answer" in exchange
        assert "first question" not in exchange

    def test_extract_last_exchange_single_user(self):
        messages = [
            Message(role="user", content="only question"),
        ]
        exchange = _extract_last_exchange(messages)
        assert "only question" in exchange

    def test_parse_create_result(self):
        content = json.dumps([{
            "action": "create",
            "name": "user-pref",
            "type": "user",
            "description": "User likes short answers",
            "content": "The user prefers concise responses.",
        }])
        results = _parse_update_results(content)
        assert len(results) == 1
        assert results[0].action == "create"
        assert results[0].name == "user-pref"
        assert results[0].type == MemoryType.USER

    def test_parse_none_action_filtered(self):
        content = json.dumps([
            {"action": "none", "name": ""},
            {"action": "create", "name": "x", "type": "project", "description": "d", "content": "c"},
        ])
        results = _parse_update_results(content)
        assert len(results) == 1
        assert results[0].action == "create"

    def test_parse_malformed_json(self):
        results = _parse_update_results("not json at all")
        assert results == []

    def test_parse_json_in_text(self):
        content = 'some text before\n[{"action": "delete", "name": "old-note"}]\nsome text after'
        results = _parse_update_results(content)
        assert len(results) == 1
        assert results[0].action == "delete"
        assert results[0].name == "old-note"

    def test_update_async_no_provider(self):
        d = Path(tempfile.mkdtemp())
        store = MemoryStore(d)
        idx = MemoryIndex(d)
        updater = MemoryUpdater(
            project_memory_dir=d / "project",
            user_memory_dir=d / "user",
            store=store,
            index=idx,
        )
        task = updater.update_async(
            [Message(role="user", content="hello")],
            provider=None,
        )
        assert task is None

    async def test_update_async_with_mock_provider(self):
        d = Path(tempfile.mkdtemp())
        store = MemoryStore(d)
        idx = MemoryIndex(d)
        # 测试中项目级和用户级用同一目录，方便验证
        updater = MemoryUpdater(
            project_memory_dir=d,
            user_memory_dir=d,
            store=store,
            index=idx,
        )

        class MockProvider:
            async def achat(self, messages, tools=None, system=None):
                from opcode_cli.provider.base import StreamChunk
                yield StreamChunk(
                    content=json.dumps([{
                        "action": "create",
                        "name": "test-memory",
                        "type": "user",
                        "description": "test description",
                        "content": "test content",
                    }]),
                    finish_reason="stop",
                )

        # 至少需要 MEMORY_EXTRACTION_INTERVAL (5) 条消息才能触发提取
        messages = [
            Message(role="user", content="msg1"),
            Message(role="assistant", content="r1"),
            Message(role="user", content="msg2"),
            Message(role="assistant", content="r2"),
            Message(role="user", content="msg3"),
            Message(role="assistant", content="r3"),
            Message(role="user", content="I prefer short answers"),
            Message(role="assistant", content="OK, I'll keep it short"),
        ]

        task = updater.update_async(messages, MockProvider())
        assert task is not None

        # 等待异步任务完成
        await task

        # 检查记忆文件是否创建
        note = store.read("test-memory", MemoryType.USER)
        assert note is not None
        assert note.description == "test description"
        assert note.content == "test content"

        # 检查索引是否更新
        index_text = idx.load_index()
        assert "test-memory" in index_text
