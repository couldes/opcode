from __future__ import annotations

from textual.widgets import Static

from opcode_cli.tui.formatting import format_diff, format_result_detail, format_tool_result


class TimelineNode(Static):
    """Base class for all timeline widgets."""

    def __init__(self, text: str = "", *, classes: str = "") -> None:
        super().__init__(text)
        self.can_focus = False
        if classes:
            self.add_class(classes)


class UserMsgNode(TimelineNode):
    """User message node in the timeline."""

    def __init__(self, text: str) -> None:
        super().__init__(f"[bold cyan]⏺ {text}[/bold cyan]", classes="user-msg")


class NotificationNode(TimelineNode):
    """Compact system notification (offload, summarize, error, etc.)."""

    def __init__(self, text: str) -> None:
        super().__init__(f"[dim]⏺ {text}[/dim]", classes="notification")


class TextNode(TimelineNode):
    """Streaming text block with incremental append support."""

    def __init__(self) -> None:
        super().__init__("", classes="text-node")
        self._buf = ""

    def append(self, text: str) -> None:
        self._buf += text
        self.update(f"[bold green]⏺ opcode[/bold green]\n{self._buf}")

    def finalize(self) -> None:
        """Mark streaming complete. Text remains displayed."""

    @property
    def content(self) -> str:
        return self._buf


class ThinkingNode(TimelineNode):
    """Thinking content with expand/collapse toggle."""

    def __init__(self) -> None:
        super().__init__("", classes="thinking-node")
        self._expanded = True
        self._buf = ""
        self.can_focus = False  # Toggle via click, not focus
        self._update_display()

    def _update_display(self) -> None:
        if self._expanded:
            header = "[dim][-] Thinking[/dim]"
            body = f"[dim italic]{self._buf}[/dim italic]" if self._buf else ""
            self.update(f"{header}\n{body}" if body else header)
        else:
            self.update("[dim][+] Thinking[/dim]")

    def append(self, text: str) -> None:
        self._buf += text
        self._update_display()

    def on_click(self) -> None:
        self._expanded = not self._expanded
        self._update_display()

    @property
    def has_content(self) -> bool:
        return bool(self._buf)


class ToolCallNode(TimelineNode):
    """Tool call node with state machine: pending -> completed/error.

    Supports expand/collapse for long results.
    """

    THRESHOLD = 5  # lines threshold for collapsing

    def __init__(self, tool_id: str, name: str) -> None:
        super().__init__("", classes="tool-call")
        self.tool_id = tool_id
        self.tool_name = name
        self._state = "pending"
        self._call_text = ""
        self._result_text = ""
        self._full_content = ""
        self._result_success = True
        self._result_error: str | None = None
        self._expanded = False

    def set_pending(self, call_text: str) -> None:
        """Show the tool call with a loading indicator."""
        self._call_text = call_text
        self._state = "pending"
        self._update_display()

    def set_result(self, success: bool, content: str, error: str | None = None) -> None:
        """Replace loading indicator with result summary."""
        self._state = "completed" if success else "error"
        self._result_success = success
        self._full_content = content
        self._result_error = error
        self._result_text = format_tool_result(self.tool_name, success, content, error)
        self._expanded = False
        self._update_display()

    def _update_display(self) -> None:
        if self._state == "pending":
            self.update(f"{self._call_text}\n[dim]⎿ ...[/dim]")
            self.remove_class("tool-error")
            self.add_class("tool-pending")
            return

        self.remove_class("tool-pending")
        if not self._result_success:
            self.add_class("tool-error")

        lines = [self._call_text, self._result_text]

        if self._expanded and self._full_content:
            detail, _ = format_result_detail(self._full_content, max_lines=9999)
            diff = format_diff(self._full_content)
            if diff:
                lines.append(diff)
            else:
                lines.append(f"[dim]{detail}[/dim]")
            lines.append("[dim](Enter to collapse)[/dim]")
        elif self._full_content:
            detail, total = format_result_detail(self._full_content, self.THRESHOLD)
            if total > self.THRESHOLD:
                lines.append(f"[dim]{detail}[/dim]")

        self.update("\n".join(lines))

    def _on_key(self, event) -> None:
        if event.key == "enter" and self._state != "pending" and self._full_content:
            event.stop()
            self._expanded = not self._expanded
            self._update_display()

    @property
    def is_resolved(self) -> bool:
        return self._state in ("completed", "error")
