import asyncio
from collections.abc import AsyncIterator

from opcode_cli.agent.batcher import ToolBatcher
from opcode_cli.agent.collector import StreamCollector
from opcode_cli.agent.events import (
    AgentEvent,
    CacheMetricsEvent,
    CompressionSkippedEvent,
    DoneEvent,
    ErrorEvent,
    OffloadEvent,
    PermissionPromptEvent,
    ProgressEvent,
    SummarizeEvent,
    TokenUsageEvent,
    ToolResultEvent,
)
from opcode_cli.agent.plan_mode import PlanMode
from opcode_cli.permission.checker import PermissionChecker
from opcode_cli.permission.rules import Rule
from opcode_cli.prompt.builder import SystemPromptBuilder
from opcode_cli.prompt.injector import PlanModeInjector
from opcode_cli.prompt.reminder import system_reminder
from opcode_cli.prompt.tracker import CacheTracker
from opcode_cli.provider.anthropic import AnthropicProvider
from opcode_cli.context.manager import CompressionDecision, ContextManager
from opcode_cli.provider.base import BaseProvider, Message, ToolCall
from opcode_cli.tools.base import BaseTool, ToolResult
from opcode_cli.tools.registry import ToolRegistry


class Agent:
    def __init__(
        self,
        provider: BaseProvider,
        registry: ToolRegistry,
        max_iterations: int = 25,
        max_unknown_tools: int = 3,
        builder: SystemPromptBuilder | None = None,
        injector: PlanModeInjector | None = None,
        env_context: str = "",
        permission_checker: PermissionChecker | None = None,
        mcp_manager: object | None = None,
        context_manager: ContextManager | None = None,
        archiver: object | None = None,
        memory_updater: object | None = None,
        skills_manager: object | None = None,
        hook_runner: object | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._max_iterations = max_iterations
        self._max_unknown_tools = max_unknown_tools
        self._plan_mode: PlanMode | None = None
        self._builder = builder
        self._injector = injector
        self._env_context = env_context
        self._tracker = CacheTracker()
        self._cancelled = asyncio.Event()
        self._permission_checker = permission_checker
        self._mcp_manager = mcp_manager
        self._context_manager = context_manager
        self._archiver = archiver
        self._memory_updater = memory_updater
        self._skills_manager = skills_manager
        self._hook_runner = hook_runner
        self._permission_response: asyncio.Event | None = None
        self._permission_decision: str = ""
        self._session_active: bool = False
        self.messages: list[Message] = []

    @property
    def messages_list(self) -> list[Message]:
        return list(self.messages)

    @property
    def plan_mode(self) -> PlanMode | None:
        return self._plan_mode

    @property
    def tracker(self) -> CacheTracker:
        return self._tracker

    def set_env_context(self, env_context: str) -> None:
        self._env_context = env_context

    def cancel(self) -> None:
        self._cancelled.set()

    def set_plan_mode(self, plan_mode: PlanMode | None) -> None:
        self._plan_mode = plan_mode

    def respond_to_permission(self, decision: str) -> None:
        self._permission_decision = decision
        if self._permission_response:
            self._permission_response.set()

    async def _run_context_checks(self) -> AsyncIterator[AgentEvent]:
        """在 API 请求前执行上下文压缩检查。

        放在 ProgressEvent 之前执行，确保每次迭代 token 预算在可控范围。
        """
        if not self._context_manager:
            return

        decision = await self._context_manager.before_request(
            self.messages, provider=self._provider, manual=False
        )

        if decision.did_offload:
            yield OffloadEvent(count=decision.offloaded_count)
        if decision.summary_broken:
            yield CompressionSkippedEvent(reason="broken")
        if decision.did_summarize:
            after = self._context_manager.estimator.estimate(self.messages)
            yield SummarizeEvent(
                summarized_count=decision.summarized_count,
                total_before=decision.total_tokens,
                total_after=after,
            )

    async def compact_manual(self) -> CompressionDecision | None:
        """用户手动触发压缩（/compact 命令）。

        安全余量收窄到 3K。
        """
        if not self._context_manager:
            return None
        return await self._context_manager.before_request(
            self.messages, provider=self._provider, manual=True
        )

    def save_session(self) -> int:
        """将当前 messages 全量写入 JSONL，返回消息数。"""
        if not self._archiver:
            return 0
        self._archiver.write_full(self.messages)
        return self._archiver.message_count

    async def load_session(self, session_id: str) -> list[str]:
        """从 JSONL 恢复会话，返回警告列表。"""
        from opcode_cli.session.recovery import recover

        if self._archiver is None:
            return ["archiver not available"]

        sessions_dir = self._archiver._dir
        result = await recover(
            sessions_dir, session_id,
            context_manager=self._context_manager,
        )
        self.messages = result.messages
        return result.warnings

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        if self._cancelled.is_set():
            yield DoneEvent(finish_reason="cancelled")
            return
        self._cancelled.clear()

        # --- Hook: session_start (first run only) ---
        if not self._session_active and self._hook_runner:
            self._session_active = True
            await self._hook_runner.fire("session_start", {
                "provider_type": type(self._provider).__name__,
                "model": getattr(self._provider, "_model", "unknown"),
            })

        self.messages.append(Message(role="user", content=user_input))

        # --- Hook: user_input ---
        if self._hook_runner:
            await self._hook_runner.fire("user_input", {
                "input_text": user_input,
                "input_length": len(user_input),
                "is_command": user_input.startswith("/"),
            })

        unknown_streak = 0

        for iteration in range(1, self._max_iterations + 1):
            if self._cancelled.is_set():
                yield DoneEvent(finish_reason="cancelled")
                return

            # 记录本迭代前的消息数，用于迭代末存档
            msg_count_before = len(self.messages)

            # --- Hook: iteration_start ---
            if self._hook_runner:
                await self._hook_runner.fire("iteration_start", {
                    "iteration": iteration,
                    "max_iterations": self._max_iterations,
                    "active_tools": [t.name for t in self._registry.list_tools()],
                })

            # API 请求前执行上下文压缩检查
            async for ctx_event in self._run_context_checks():
                yield ctx_event

            yield ProgressEvent(iteration=iteration, max_iterations=self._max_iterations)

            if self._mcp_manager and iteration == 1:
                try:
                    await self._mcp_manager.ensure_registered(self._registry)
                except Exception as e:
                    yield ErrorEvent(message=f"MCP init error: {e}")

            tools = self._build_tools()

            system_text = ""
            if self._builder:
                system_text = self._builder.get_system_text(self._env_context)

            chat_messages = list(self.messages)
            if self._injector and self._plan_mode:
                instruction = self._plan_mode.get_instruction(iteration)
                if instruction:
                    chat_messages.append(system_reminder(instruction))
            if self._skills_manager:
                skills_content = self._skills_manager.get_active_skills_content()
                if skills_content:
                    chat_messages.append(system_reminder(skills_content))
            # --- Hook: prompt injection ---
            if self._hook_runner:
                for text in self._hook_runner.pending_prompts():
                    chat_messages.append(system_reminder(text))
                for text in self._hook_runner.consume_once_prompts():
                    chat_messages.append(system_reminder(text))

            collector = StreamCollector()
            try:
                async for event in collector.collect(
                    self._provider.achat(
                        chat_messages, tools=tools,
                        system=system_text if system_text else None,
                    )
                ):
                    yield event
            except Exception as e:
                yield ErrorEvent(message=str(e))
                # --- Hook: error ---
                if self._hook_runner:
                    await self._hook_runner.fire("error", {
                        "error_message": str(e),
                        "error_type": type(e).__name__,
                        "iteration": iteration,
                    })
                yield DoneEvent(finish_reason="stream_error")
                return

            if isinstance(self._provider, AnthropicProvider):
                usage = self._provider.last_usage
                if usage:
                    metrics = self._tracker.parse_from_response({"usage": usage})
                    self._tracker.record(metrics)
                    yield CacheMetricsEvent(
                        cache_creation_input_tokens=metrics.cache_creation_input_tokens,
                        cache_read_input_tokens=metrics.cache_read_input_tokens,
                        input_tokens=metrics.input_tokens,
                    )
                    if self._context_manager and usage.get("input_tokens"):
                        self._context_manager.update_anchor(
                            usage["input_tokens"], self.messages,
                        )

            tool_calls = collector.tool_calls

            if not tool_calls:
                self.messages.append(Message(
                    role="assistant",
                    content=collector.content,
                    thinking=collector.thinking if collector.thinking else None,
                ))
                # --- Hook: assistant_response ---
                if self._hook_runner:
                    await self._hook_runner.fire("assistant_response", {
                        "response_text": collector.content,
                        "response_length": len(collector.content),
                        "thinking_length": len(collector.thinking or ""),
                        "finish_reason": "stop",
                    })
                # 存档最后的 assistant 消息 + 异步触发记忆更新
                if self._archiver:
                    new_messages = self.messages[msg_count_before:]
                    if new_messages:
                        self._archiver.append(new_messages)
                if self._memory_updater:
                    self._memory_updater.update_async(self.messages, self._provider)
                yield DoneEvent(finish_reason="stop")
                return

            any_unknown = any(
                self._is_unknown_tool(tc.name) for tc in tool_calls
            )
            if any_unknown:
                unknown_streak += 1
                if unknown_streak >= self._max_unknown_tools:
                    yield DoneEvent(finish_reason="unknown_tool")
                    return
            else:
                unknown_streak = 0

            self.messages.append(Message(
                role="assistant",
                content=collector.content,
                tool_calls=tool_calls,
            ))

            allowed_calls: list[ToolCall] = []
            for tc in tool_calls:
                if self._permission_checker is None:
                    allowed_calls.append(tc)
                    continue

                result = self._permission_checker.check(tc)
                if result == "allow":
                    allowed_calls.append(tc)
                elif result == "deny":
                    self.messages.append(Message(
                        role="tool",
                        content="Error: blocked by permission policy",
                        tool_call_id=tc.id,
                        name=tc.name,
                    ))
                    yield ToolResultEvent(
                        tool_id=tc.id, name=tc.name,
                        result=ToolResult(success=False, content="", error="blocked by permission policy"),
                    )
                else:  # ask_user
                    from opcode_cli.permission.rules import _serialize_args
                    yield PermissionPromptEvent(
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        args_str=_serialize_args(tc.input),
                    )
                    self._permission_response = asyncio.Event()
                    self._permission_decision = ""
                    try:
                        await asyncio.wait_for(
                            self._permission_response.wait(),
                            timeout=60.0,
                        )
                    except asyncio.TimeoutError:
                        self._permission_decision = "deny"
                    self._permission_response = None

                    if self._permission_decision == "deny":
                        self.messages.append(Message(
                            role="tool",
                            content="Error: denied by user",
                            tool_call_id=tc.id,
                            name=tc.name,
                        ))
                        yield ToolResultEvent(
                            tool_id=tc.id, name=tc.name,
                            result=ToolResult(success=False, content="", error="denied by user"),
                        )
                    else:
                        allowed_calls.append(tc)
                        if self._permission_decision == "allow_session":
                            if self._permission_checker is not None:
                                self._permission_checker.add_session_rule(
                                    Rule(
                                        tool_name=tc.name,
                                        pattern=_serialize_args(tc.input),
                                        action="allow",
                                    )
                                )

            # --- Hook: tool_pre_execute (check before batcher) ---
            if self._hook_runner and allowed_calls:
                for tc in list(allowed_calls):
                    fire_result = await self._hook_runner.fire("tool_pre_execute", {
                        "tool_name": tc.name,
                        "tool_args": tc.input,
                        "tool_call_id": tc.id,
                        "is_read_only": getattr(
                            self._registry.get(tc.name), "read_only", False
                        ) if not self._is_unknown_tool(tc.name) else False,
                    })
                    if fire_result.intercept:
                        allowed_calls.remove(tc)
                        yield ToolResultEvent(
                            tool_id=tc.id, name=tc.name,
                            result=ToolResult(
                                success=False, content="", error=fire_result.intercept,
                            ),
                        )
                        self.messages.append(Message(
                            role="tool",
                            content=f"Error: {fire_result.intercept}",
                            tool_call_id=tc.id,
                            name=tc.name,
                        ))

            if allowed_calls:
                batcher = ToolBatcher(self._registry)
                async for event in batcher.execute(allowed_calls):
                    yield event
                    self.messages.append(Message(
                        role="tool",
                        content=event.result.content
                        if event.result.success
                        else f"Error: {event.result.error}",
                        tool_call_id=event.tool_id,
                        name=event.name,
                    ))
                    # --- Hook: tool_post_execute ---
                    if self._hook_runner:
                        await self._hook_runner.fire("tool_post_execute", {
                            "tool_name": event.name,
                            "tool_call_id": event.tool_id,
                            "success": event.result.success,
                            "result_content": event.result.content[:500],
                        })

            # 存档本轮新增的消息
            if self._archiver:
                new_messages = self.messages[msg_count_before:]
                if new_messages:
                    self._archiver.append(new_messages)

            # --- Hook: iteration_end ---
            if self._hook_runner:
                await self._hook_runner.fire("iteration_end", {
                    "iteration": iteration,
                    "finish_reason": "tool_use" if tool_calls else "stop",
                    "tool_calls_count": len(tool_calls) if tool_calls else 0,
                })

        yield DoneEvent(finish_reason="max_iterations")

    def _is_unknown_tool(self, name: str) -> bool:
        try:
            self._registry.get(name)
            return False
        except KeyError:
            return True

    def _build_tools(self) -> list[dict] | None:
        if self._plan_mode is not None:
            tools = self._plan_mode.get_tools()
        else:
            tools = self._registry.list_tools()

        if self._skills_manager:
            whitelist = self._skills_manager.get_whitelist()
            if whitelist is not None:
                tools = [
                    t for t in tools
                    if getattr(t, "system_level", False) or t.name in whitelist
                ]

        if not tools:
            return None

        if isinstance(self._provider, AnthropicProvider):
            return [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]
