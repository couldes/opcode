import asyncio
from collections.abc import AsyncIterator

from opcode_cli.agent.batcher import ToolBatcher
from opcode_cli.agent.collector import StreamCollector
from opcode_cli.agent.events import (
    AgentEvent,
    CacheMetricsEvent,
    DoneEvent,
    ErrorEvent,
    PermissionPromptEvent,
    ProgressEvent,
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
        self._permission_response: asyncio.Event | None = None
        self._permission_decision: str = ""
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

    async def run(self, user_input: str) -> AsyncIterator[AgentEvent]:
        if self._cancelled.is_set():
            yield DoneEvent(finish_reason="cancelled")
            return
        self._cancelled.clear()
        self.messages.append(Message(role="user", content=user_input))

        unknown_streak = 0

        for iteration in range(1, self._max_iterations + 1):
            if self._cancelled.is_set():
                yield DoneEvent(finish_reason="cancelled")
                return

            yield ProgressEvent(iteration=iteration, max_iterations=self._max_iterations)

            tools = self._build_tools()

            system_text = ""
            if self._builder:
                system_text = self._builder.get_system_text(self._env_context)

            chat_messages = list(self.messages)
            if self._injector and self._plan_mode:
                instruction = self._plan_mode.get_instruction(iteration)
                if instruction:
                    chat_messages.append(system_reminder(instruction))

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

            tool_calls = collector.tool_calls

            if not tool_calls:
                self.messages.append(Message(
                    role="assistant",
                    content=collector.content,
                    thinking=collector.thinking if collector.thinking else None,
                ))
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
