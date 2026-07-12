from __future__ import annotations

import sys
from collections.abc import AsyncIterator

from textual.containers import VerticalScroll

from opcode_cli.agent.events import (
    AgentEvent,
    CompressionSkippedEvent,
    DoneEvent,
    ErrorEvent,
    OffloadEvent,
    PermissionPromptEvent,
    SubAgentResultEvent,
    SummarizeEvent,
    TeamApprovalEvent,
    TextDelta,
    ThinkingDelta,
    ToolCallInput,
    ToolCallStart,
    ToolResultEvent,
)
from opcode_cli.tui.formatting import format_tool_call
from opcode_cli.tui.widgets import (
    NotificationNode,
    TextNode,
    ThinkingNode,
    ToolCallNode,
    UserMsgNode,
)
from opcode_cli.tui.widgets.inline_permission import PermissionWidget


class TimelineRenderer:
    """Maps AgentEvent stream to timeline widget operations.

    Core fix: instead of one pre-mounted assistant widget,
    each event creates or updates a widget in chronological order.
    """

    def __init__(self, chat: VerticalScroll, input_widget=None) -> None:
        self._chat = chat
        self._input = input_widget
        self._current_text: TextNode | None = None
        self._current_thinking: ThinkingNode | None = None
        self._pending_tools: dict[str, ToolCallNode] = {}
        self._tool_names: dict[str, str] = {}
        self._buf = ""  # accumulated text for return value

    def _is_at_bottom(self) -> bool:
        return self._chat.scroll_offset.y >= self._chat.max_scroll_y - 2

    def _scroll_if_at_bottom(self) -> None:
        if self._is_at_bottom():
            self._chat.scroll_end(animate=False)

    def _close_text(self) -> None:
        if self._current_text is not None:
            self._current_text.finalize()
            self._current_text = None

    def _close_thinking(self) -> None:
        if self._current_thinking is not None:
            self._current_thinking = None

    async def mount_node(self, node) -> None:
        await self._chat.mount(node)

    async def render(self, event_stream: AsyncIterator[AgentEvent]) -> str:
        """Consume event stream and update the timeline.

        Returns accumulated text content for _last_response.
        """
        async for event in event_stream:
            await self._handle_event(event)
        return self._buf

    async def _handle_event(self, event: AgentEvent) -> None:
        if isinstance(event, TextDelta):
            self._buf += event.content
            if self._current_text is None:
                self._current_text = TextNode()
                await self.mount_node(self._current_text)
            self._current_text.append(event.content)
            self._scroll_if_at_bottom()
            return

        if isinstance(event, ThinkingDelta):
            if self._current_thinking is None:
                self._current_thinking = ThinkingNode()
                await self.mount_node(self._current_thinking)
            self._current_thinking.append(event.content)
            self._scroll_if_at_bottom()
            return

        if isinstance(event, ToolCallStart):
            self._close_text()
            self._close_thinking()
            self._tool_names[event.tool_id] = event.name
            return

        if isinstance(event, ToolCallInput):
            self._close_text()
            self._close_thinking()
            name = self._tool_names.get(event.tool_id, "tool")
            call_text = format_tool_call(name, event.input_delta)
            node = ToolCallNode(event.tool_id, name)
            node.set_pending(call_text)
            self._pending_tools[event.tool_id] = node
            await self.mount_node(node)
            self._scroll_if_at_bottom()
            return

        if isinstance(event, ToolResultEvent):
            self._close_text()
            self._close_thinking()
            node = self._pending_tools.pop(event.tool_id, None)
            if node is not None:
                node.set_result(
                    event.result.success,
                    event.result.content,
                    event.result.error,
                )
            self._scroll_if_at_bottom()
            return

        if isinstance(event, PermissionPromptEvent):
            self._close_text()
            self._close_thinking()
            if not sys.stdin.isatty():
                if event.future and not event.future.done():
                    event.future.set_result("deny")
                return
            widget = PermissionWidget(
                tool_name=event.tool_name,
                description=event.description,
                future=event.future,
            )
            await self.mount_node(widget)
            self._chat.scroll_end(animate=False)
            # Keep the input focused so the user types y/s/d/n + Enter there
            if self._input is not None:
                self._input.disabled = False
                self._input._pending_permission = widget
                if not self._input.has_focus:
                    self._input.focus()
            return

        if isinstance(event, DoneEvent):
            had_text = self._current_text is not None
            self._close_text()
            self._close_thinking()
            if event.finish_reason == "stop" and event.content and not had_text:
                # Final content without streaming text — create a TextNode
                self._current_text = TextNode()
                self._current_text.append(event.content)
                await self.mount_node(self._current_text)
                self._close_text()
            return

        if isinstance(event, ErrorEvent):
            await self.mount_node(
                NotificationNode(f"[red]Error: {event.message}[/red]")
            )
            self._scroll_if_at_bottom()
            return

        if isinstance(event, OffloadEvent):
            await self.mount_node(
                NotificationNode(f"Offloaded {event.count} tool results to disk")
            )
            self._scroll_if_at_bottom()
            return

        if isinstance(event, SummarizeEvent):
            await self.mount_node(
                NotificationNode(
                    f"Summarized {event.summarized_count} messages "
                    f"({event.total_before // 1000}K -> {event.total_after // 1000}K tokens)"
                )
            )
            self._scroll_if_at_bottom()
            return

        if isinstance(event, CompressionSkippedEvent):
            if event.reason == "broken":
                await self.mount_node(
                    NotificationNode("Compression skipped: summarizer broken")
                )
                self._scroll_if_at_bottom()
            return

        if isinstance(event, SubAgentResultEvent):
            status_icon = "OK" if event.success else "FAIL"
            await self.mount_node(
                NotificationNode(
                    f"{status_icon} Sub-agent '{event.agent_name}' "
                    f"({event.task_id}) completed "
                    f"({event.input_tokens:,} in / {event.output_tokens:,} out)"
                )
            )
            self._scroll_if_at_bottom()
            return

        if isinstance(event, TeamApprovalEvent):
            task_ids_str = ", ".join(event.task_ids) if event.task_ids else "none"
            await self.mount_node(
                NotificationNode(
                    f"[bold cyan][TEAM][/bold cyan] Approval request from "
                    f"[bold]{event.sender}[/bold]: "
                    f"{event.plan_summary[:120]} "
                    f"(tasks: {task_ids_str})"
                )
            )
            self._scroll_if_at_bottom()
            return
