"""OffloadManager 单元测试。"""

from pathlib import Path

from opcode_cli.context import OffloadManager
from opcode_cli.provider.base import Message


def _make_tool_msg(content: str, tool_name: str = "read_file") -> Message:
    """创建一条 tool result 消息。"""
    return Message(role="tool", content=content, tool_call_id="1", name=tool_name)


class TestOffloadManager:
    def test_single_under_threshold(self, tmp_path: Path):
        mgr = OffloadManager(str(tmp_path), "sess1", single_threshold=4096)
        msgs = [_make_tool_msg("small content")]
        new_msgs, records = mgr.check(msgs)
        assert records == []

    def test_single_over_threshold(self, tmp_path: Path):
        mgr = OffloadManager(str(tmp_path), "sess1", single_threshold=100)
        large = "x" * 500
        msgs = [_make_tool_msg(large)]
        new_msgs, records = mgr.check(msgs)
        assert len(records) == 1
        assert new_msgs[0].offloaded is True
        assert new_msgs[0].content.startswith("[Content offloaded to")

    def test_idempotent(self, tmp_path: Path):
        mgr = OffloadManager(str(tmp_path), "sess1", single_threshold=100)
        large = "x" * 500
        msgs = [_make_tool_msg(large)]
        # 第一次触发
        new_msgs1, records1 = mgr.check(msgs)
        assert len(records1) == 1
        # 第二次不应重复处理（传入第一次返回的已 offload 消息）
        new_msgs2, records2 = mgr.check(new_msgs1)
        assert records2 == []

    def test_total_threshold_triggers(self, tmp_path: Path):
        mgr = OffloadManager(str(tmp_path), "sess1", single_threshold=10000, total_threshold=200)
        msgs = [
            _make_tool_msg("a" * 600, "tool_a"),   # ~214 tokens
            _make_tool_msg("b" * 400, "tool_b"),   # ~144 tokens
        ]
        new_msgs, records = mgr.check(msgs)
        # 合计 ~358 > 200，应触发存盘
        assert len(records) >= 1
        # 最大的先被存盘
        assert new_msgs[0].offloaded

    def test_user_message_not_affected(self, tmp_path: Path):
        mgr = OffloadManager(str(tmp_path), "sess1", single_threshold=100)
        msgs = [Message(role="user", content="x" * 1000)]
        new_msgs, records = mgr.check(msgs)
        assert records == []
        assert new_msgs[0].offloaded is False

    def test_offload_file_content(self, tmp_path: Path):
        mgr = OffloadManager(str(tmp_path), "sess1", single_threshold=100)
        original = "hello world " * 50
        msgs = [_make_tool_msg(original)]
        new_msgs, records = mgr.check(msgs)
        assert len(records) == 1
        file_path = records[0].file_path
        saved = Path(file_path).read_text(encoding="utf-8")
        assert saved == original

    def test_offload_message_index(self, tmp_path: Path):
        mgr = OffloadManager(str(tmp_path), "sess1", single_threshold=100)
        msgs = [
            _make_tool_msg("small"),
            _make_tool_msg("x" * 500, "big_tool"),
            _make_tool_msg("tiny"),
        ]
        new_msgs, records = mgr.check(msgs)
        assert len(records) == 1
        assert records[0].message_index == 1
        assert records[0].tool_name == "big_tool"
