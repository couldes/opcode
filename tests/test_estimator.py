"""Token 估算器单元测试。"""

from opcode_cli.context import TokenEstimator
from opcode_cli.provider.base import Message


class TestTokenEstimator:
    def test_estimate_text_empty(self):
        assert TokenEstimator.estimate_text("") == 4

    def test_estimate_text_non_empty(self):
        result = TokenEstimator.estimate_text("hello world")
        assert result > 4
        assert result == int(11 * 0.35) + 4

    def test_estimate_no_anchor(self):
        estimator = TokenEstimator()
        msgs = [Message(role="user", content="hi")]
        result = estimator.estimate(msgs)
        assert result > 0

    def test_estimate_with_anchor(self):
        estimator = TokenEstimator()
        msgs = [Message(role="user", content="hello"), Message(role="assistant", content="world")]
        estimator.update_anchor(original := 100, msgs)
        result = estimator.estimate(msgs)
        assert result == 100

    def test_estimate_incremental_after_anchor(self):
        estimator = TokenEstimator()
        msgs = [Message(role="user", content="hi")]
        estimator.update_anchor(50, msgs)
        msgs.append(Message(role="assistant", content="hello world this is a longer response"))
        result = estimator.estimate(msgs)
        assert result > 50

    def test_estimate_empty_list(self):
        estimator = TokenEstimator()
        assert estimator.estimate([]) == 0

    def test_update_anchor_updates_state(self):
        estimator = TokenEstimator()
        msgs = [Message(role="user", content="test")]
        estimator.update_anchor(200, msgs)
        assert estimator._anchor_total == 200
        assert estimator._anchor_messages_count == 1
