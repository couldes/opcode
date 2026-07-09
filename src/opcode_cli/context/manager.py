from dataclasses import dataclass

from opcode_cli.context.estimator import TokenEstimator
from opcode_cli.context.offload import OffloadManager
from opcode_cli.context.summary import SummaryEngine
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

    @property
    def estimator(self) -> TokenEstimator:
        return self._estimator

    @property
    def summary_engine(self) -> SummaryEngine:
        return self._summary

    async def before_request(
        self,
        messages: list[Message],
        provider: BaseProvider | None = None,
        manual: bool = False,
    ) -> CompressionDecision:
        """API 请求前执行上下文压缩检查。

        manual=True 时安全余量收窄到 3K（用户手动触发）。
        """
        total = self._estimator.estimate(messages)
        safety = 3000 if manual else 13000
        window = self._context_window

        decision = CompressionDecision(
            total_tokens=total,
            context_window=window,
            safety_margin=safety,
            summary_broken=self._summary.broken,
        )

        # F3: 大工具结果存盘
        records = self._offload.check(messages)
        if records:
            decision.did_offload = True
            decision.offloaded_count = len(records)
            total = self._estimator.estimate(messages)
            decision.total_tokens = total

        # F4: 对话摘要（仅在 F3 后仍超窗口时）
        if total + safety > window:
            if self._summary.broken:
                decision.summary_broken = True
                return decision

            if not self._summary.should_summarize(messages):
                return decision

            summary_msgs = self._summary.build_summary_prompt(messages)
            if not summary_msgs:
                return decision

            summary_text = await self._call_summary_llm(summary_msgs, provider)

            if summary_text is None:
                self._summary._failure_count += 1
                if self._summary._failure_count >= 3:
                    self._summary._broken = True
                    decision.summary_broken = True
                return decision

            # 成功 — 重置失败计数
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
        """调用 LLM 生成摘要。

        使用 provider 的 chat() 方法（非流式），不传入 tools。
        """
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
        """更新 Token 估算锚点。"""
        self._estimator.update_anchor(api_input_tokens, messages)

    def reset_summary(self) -> None:
        """重置摘要熔断状态。"""
        self._summary.reset()
