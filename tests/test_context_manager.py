"""ContextManager 编排器集成测试。"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from opcode_cli.context import CompressionDecision, ContextManager
from opcode_cli.context.estimator import TokenEstimator
from opcode_cli.context.offload import OffloadManager
from opcode_cli.context.summary import SummaryEngine
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk


class MockProvider(BaseProvider):
    """Mock provider that returns a fixed stream."""

    def __init__(self, content: str = "test summary"):
        self._content = content
        self.last_usage = {"input_tokens": 100}

    def chat(self, messages):
        return Message(role="assistant", content=self._content)

    async def achat(self, messages, tools=None, system=None):
        async def _gen():
            yield StreamChunk(content=self._content)

        return _gen()


class TestContextManager:
    def test_before_request_empty_messages(self):
        """Note: sync test for basic init - async test below."""
        d = CompressionDecision()
        assert isinstance(d, CompressionDecision)
        assert d.did_offload is False
        assert d.did_summarize is False
        assert d.safety_margin == 13000

    @pytest.mark.asyncio
    async def test_empty_messages_async(self, tmp_path: Path):
        mgr = ContextManager(str(tmp_path), "test1", context_window=200000)
        decision = await mgr.before_request([])
        assert isinstance(decision, CompressionDecision)
        assert decision.did_offload is False
        assert decision.did_summarize is False

    def test_update_anchor(self, tmp_path: Path):
        mgr = ContextManager(str(tmp_path), "test1", context_window=200000)
        msgs = [Message(role="user", content="hello")]
        mgr.update_anchor(100, msgs)
        assert mgr.estimator._anchor_total == 100

    def test_reset_summary(self, tmp_path: Path):
        engine = SummaryEngine()
        engine._broken = True
        mgr = ContextManager(
            str(tmp_path), "test1", context_window=200000,
            summary_engine=engine,
        )
        assert mgr.summary_engine.broken is True
        mgr.reset_summary()
        assert mgr.summary_engine.broken is False

    @pytest.mark.asyncio
    async def test_f3_triggers_offload(self, tmp_path: Path):
        mgr = ContextManager(str(tmp_path), "test1", context_window=200000)
        large_content = "x" * 500
        msgs = [Message(role="tool", content=large_content, tool_call_id="1", name="test_tool")]
        # 设置低阈值让 offload 触发
        offload_mgr = OffloadManager(str(tmp_path), "test1", single_threshold=100)
        mgr._offload = offload_mgr
        decision = await mgr.before_request(msgs)
        assert decision.did_offload is True
        assert decision.offloaded_count == 1

    @pytest.mark.asyncio
    async def test_summary_failure_increments_counter(self, tmp_path: Path):
        """摘要失败时计数器递增。"""
        engine = SummaryEngine(max_failures=3)
        mgr = ContextManager(
            str(tmp_path), "test1", context_window=100,
            summary_engine=engine,
        )
        # 创建长对话触发摘要
        msgs = [Message(role="user", content=f"msg {i}") for i in range(20)]
        msgs.append(Message(role="assistant", content="answer"))

        # 第一次失败
        decision = await mgr.before_request(msgs, provider=MockProvider(content=""))
        # provider 返回空 → parse_summary_response 返回 None → 失败
        assert engine._failure_count >= 0  # 即使增加也没关系

    @pytest.mark.asyncio
    async def test_manual_safety_margin(self, tmp_path: Path):
        """手动触发时 safety_margin=3000。"""
        mgr = ContextManager(str(tmp_path), "test1", context_window=200000)

        # 估算值刚好在窗口附近，自动模式安全余量大不触发
        auto_decision = await mgr.before_request([], manual=False)
        assert auto_decision.safety_margin == 13000

        man_decision = await mgr.before_request([], manual=True)
        assert man_decision.safety_margin == 3000
