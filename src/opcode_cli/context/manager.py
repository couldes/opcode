from dataclasses import dataclass

from opcode_cli.context.estimator import TokenEstimator
from opcode_cli.context.offload import OffloadManager
from opcode_cli.context.summary import SummaryEngine
from opcode_cli.context.types import CompactCircuitBreaker, RecoveryState
from opcode_cli.provider.base import BaseProvider, Message


@dataclass
class CompressionDecision:
    """单次压缩检查的决策记录。"""
    total_tokens: int = 0
    context_window: int = 0
    safety_margin: int = 13000
    did_offload: bool = False
    offloaded_count: int = 0
    did_summarize: bool = False
    summarized_count: int = 0
    summary_broken: bool = False


SOFT_MARGIN = 13000   # 软阈值余量，正常触发走熔断器
HARD_MARGIN = 3000    # 硬阈值余量，强制触发跳过熔断器


class ContextManager:
    """上下文压缩编排器。

    在每次 API 请求前调用 before_request()，依次执行：
    F3 - 大工具结果存盘（预防）
    F4 - 对话摘要（兜底）
    """

    def __init__(
        self,
        project_root: str,
        session_id: str,
        context_window: int,
        estimator: TokenEstimator | None = None,
        offload_mgr: OffloadManager | None = None,
        summary_engine: SummaryEngine | None = None,
    ) -> None:
        self._estimator = estimator or TokenEstimator()
        self._offload = offload_mgr or OffloadManager(project_root, session_id)
        self._summary = summary_engine or SummaryEngine()
        self._context_window = context_window
        self._recovery = RecoveryState()
        self._circuit_breaker = CompactCircuitBreaker()

    @property
    def estimator(self) -> TokenEstimator:
        return self._estimator

    @property
    def summary_engine(self) -> SummaryEngine:
        return self._summary

    @property
    def recovery(self) -> RecoveryState:
        return self._recovery

    @property
    def circuit_breaker(self) -> CompactCircuitBreaker:
        return self._circuit_breaker

    async def before_request(
        self,
        messages: list[Message],
        provider: BaseProvider | None = None,
        manual: bool = False,
    ) -> CompressionDecision:
        """API 请求前执行上下文压缩检查。

        使用双阈值策略：
        - SOFT (13K margin)：正常触发，走熔断器保护
        - HARD (3K margin)：强制压缩，跳过熔断器
        """
        total = self._estimator.estimate(messages)
        window = self._context_window

        decision = CompressionDecision(
            total_tokens=total,
            context_window=window,
            safety_margin=SOFT_MARGIN if not manual else HARD_MARGIN,
            summary_broken=self._summary.broken,
        )

        # F3: 大工具结果存盘（三段式）
        new_messages, offload_records = self._offload.check(messages)
        if offload_records:
            decision.did_offload = True
            decision.offloaded_count = len(offload_records)
            messages[:] = new_messages  # 替换为 offload 后的副本
            total = self._estimator.estimate(messages)
            decision.total_tokens = total

        # 双阈值判断
        should_compress_soft = total + SOFT_MARGIN > window
        should_compress_hard = total + HARD_MARGIN > window

        if not should_compress_soft and not should_compress_hard:
            return decision

        # 硬阈值：强制压缩，跳过熔断器
        if should_compress_hard:
            decision.safety_margin = HARD_MARGIN
            return await self._do_compress(messages, provider, decision)

        # 软阈值：走熔断器保护
        if self._circuit_breaker.is_open():
            return decision

        return await self._do_compress(messages, provider, decision)

    async def _do_compress(
        self,
        messages: list[Message],
        provider: BaseProvider | None,
        decision: CompressionDecision,
    ) -> CompressionDecision:
        """执行压缩逻辑（F4 + recovery attachment）。"""
        if self._summary.broken:
            decision.summary_broken = True
            return decision

        if not self._summary.should_summarize(messages):
            return decision

        # 压缩前附加 RecoveryState 附件
        recovery_attachment = self._recovery.build_recovery_attachment()
        if recovery_attachment:
            messages.append(Message(
                role="user",
                content=f"[Recovery Context]\n{recovery_attachment}",
            ))

        summary_msgs = self._summary.build_summary_prompt(messages)
        if not summary_msgs:
            return decision

        summary_text = await self._call_summary_llm(summary_msgs, provider)

        if summary_text is None:
            self._circuit_breaker.record_failure()
            self._summary._failure_count += 1
            if self._summary._failure_count >= 3:
                self._summary._broken = True
                decision.summary_broken = True
            return decision

        # 成功 — 重置熔断器和失败计数
        self._circuit_breaker.record_success()
        self._summary._failure_count = 0

        summarized_count = self._summary.apply_summary(messages, summary_text)
        decision.did_summarize = True
        decision.summarized_count = summarized_count

        return decision

    async def _call_summary_llm(
        self,
        summary_msgs: list[Message],
        provider: BaseProvider | None,
    ) -> str | None:
        if provider is None:
            return None

        try:
            result = await provider.achat(summary_msgs, tools=None)
            content_parts: list[str] = []
            async for chunk in result:
                if chunk.content:
                    content_parts.append(chunk.content)
            full_content = "".join(content_parts)
            return self._summary.parse_summary_response(full_content)
        except Exception:
            return None

    def update_anchor(self, api_input_tokens: int, messages: list[Message]) -> None:
        self._estimator.update_anchor(api_input_tokens, messages)

    def reset_summary(self) -> None:
        self._summary.reset()
