from opcode_cli.provider.base import Message


class TokenEstimator:
    """轻量 Token 估算器。

    使用锚定机制：以最近一次 API 响应的 input_tokens 为锚点，
    后续新增消息按字符数 × 0.35 估算增量。
    """

    def __init__(self) -> None:
        self._anchor_total: int | None = None
        self._anchor_messages_count: int = 0
        self._anchor_messages_text_len: int = 0

    @property
    def baseline_tokens(self) -> int:
        return self._anchor_total or 0

    @property
    def anchor_count(self) -> int:
        return self._anchor_messages_count

    @staticmethod
    def estimate_text(text: str) -> int:
        """对单段文本估算 tokens。

        使用保守系数 0.35 token/字符，适合中英文混合场景。
        每条消息加 4 tokens 基础开销（role 和元数据）。
        """
        if not text:
            return 4
        return int(len(text) * 0.35) + 4

    def estimate(self, messages: list[Message]) -> int:
        """估算 messages 列表总 token 数。

        有锚点时基于锚点 + 增量估算，无锚点时全量字符估算。
        """
        if not messages:
            return 0

        current_text_len = sum(len(m.content or "") for m in messages)

        if self._anchor_total is not None:
            delta_chars = current_text_len - self._anchor_messages_text_len
            delta_msgs = len(messages) - self._anchor_messages_count
            delta_tokens = int(delta_chars * 0.35) + delta_msgs * 4
            return max(0, self._anchor_total + delta_tokens)

        return sum(self.estimate_text(m.content or "") for m in messages)

    def current_tokens(self, messages: list[Message]) -> int:
        """与 estimate() 相同，提供更明确的命名。"""
        return self.estimate(messages)

    def record_usage_anchor(
        self,
        input_tokens: int,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_creation: int = 0,
    ) -> None:
        """记录真实 API 用量锚点。"""
        self._anchor_total = input_tokens + cache_read + cache_creation + output_tokens

    def update_anchor(self, api_input_tokens: int, messages: list[Message]) -> None:
        """API 调用后，用真实 input_tokens 更新锚点。"""
        self._anchor_total = api_input_tokens
        self._anchor_messages_count = len(messages)
        self._anchor_messages_text_len = sum(len(m.content or "") for m in messages)
