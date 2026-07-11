"""SummaryEngine 单元测试。"""

import pytest

from opcode_cli.context import SummaryEngine
from opcode_cli.context.summary import ANALYSIS_DRAFT_MARKER
from opcode_cli.provider.base import Message


def _build_rounds(n: int) -> list[Message]:
    """构造 n 轮交互的 messages。"""
    msgs = []
    for i in range(n):
        msgs.append(Message(role="user", content=f"question {i}"))
        msgs.append(Message(role="assistant", content=f"answer {i}"))
    return msgs


class TestSummaryEngine:
    def test_short_conversation_no_summary(self):
        engine = SummaryEngine()
        msgs = _build_rounds(2)
        assert engine.should_summarize(msgs) is False

    def test_long_conversation_should_summarize(self):
        """8 轮交互：摘要区至少 3 条消息，应触发。"""
        engine = SummaryEngine()
        msgs = _build_rounds(8)
        assert engine.should_summarize(msgs) is True

    def test_broken_returns_false(self):
        engine = SummaryEngine()
        engine._broken = True
        msgs = _build_rounds(10)
        assert engine.should_summarize(msgs) is False

    def test_build_summary_prompt_short_conversation(self):
        engine = SummaryEngine()
        msgs = _build_rounds(2)
        prompt = engine.build_summary_prompt(msgs)
        assert prompt == []

    def test_build_summary_prompt_contains_constraints(self):
        engine = SummaryEngine()
        msgs = _build_rounds(8)
        prompt = engine.build_summary_prompt(msgs)
        assert len(prompt) == 1
        content = prompt[0].content
        assert "DO NOT call any tools" in content
        assert ANALYSIS_DRAFT_MARKER in content

    def test_parse_summary_with_marker(self):
        engine = SummaryEngine()
        content = f"draft\n{ANALYSIS_DRAFT_MARKER}\nformal text"
        result = engine.parse_summary_response(content)
        assert result == "formal text"

    def test_parse_summary_without_marker(self):
        engine = SummaryEngine()
        result = engine.parse_summary_response("plain summary")
        assert result == "plain summary"

    def test_parse_summary_empty(self):
        engine = SummaryEngine()
        assert engine.parse_summary_response("") is None
        assert engine.parse_summary_response("   ") is None

    def test_build_boundary_message(self):
        msg = SummaryEngine.build_boundary_message()
        assert msg.role == "user"
        assert "<system-reminder>" in msg.content
        assert "re-read" in msg.content

    def test_apply_summary_shortens_messages(self):
        engine = SummaryEngine()
        msgs = _build_rounds(8)
        original_len = len(msgs)
        summary = "## Summary\n\n### Files & Changes\n- test: feature\n\n### Decisions\n- x\n\n### Remaining\n- y"
        count = engine.apply_summary(msgs, summary)
        assert count > 0
        assert len(msgs) < original_len

    def test_apply_summary_contains_compressed(self):
        engine = SummaryEngine()
        msgs = _build_rounds(8)
        engine.apply_summary(msgs, "test summary")
        assert any(m.compressed for m in msgs)

    def test_apply_summary_contains_boundary(self):
        engine = SummaryEngine()
        msgs = _build_rounds(8)
        engine.apply_summary(msgs, "test summary")
        assert any("<system-reminder>" in (m.content or "") for m in msgs)

    def test_apply_summary_preserves_tail(self):
        engine = SummaryEngine()
        msgs = _build_rounds(8)
        tail = msgs[-1].content
        engine.apply_summary(msgs, "test summary")
        assert msgs[-1].content == tail

    def test_apply_summary_no_short_conversation(self):
        engine = SummaryEngine()
        msgs = _build_rounds(2)
        count = engine.apply_summary(msgs, "test")
        assert count == 0
