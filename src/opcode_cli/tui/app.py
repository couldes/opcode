import asyncio

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, TextArea

from opcode_cli.agent.agent import Agent
from opcode_cli.agent.events import (
    DoneEvent,
    ErrorEvent,
    TextDelta,
    ThinkingDelta,
    ToolCallStart,
    ToolCallInput,
    ToolResultEvent,
)


class ThinkingToggle(Static):
    """Clickable toggle for thinking content."""

    def __init__(self, content_widget: Static) -> None:
        super().__init__("", classes="thinking-toggle")
        self._expanded = True
        self._content = content_widget

    def on_click(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._content.remove_class("hidden")
            self.update("[dim][-] Thinking (click to collapse)[/dim]")
        else:
            self._content.add_class("hidden")
            self.update("[dim][+] Thinking (click to expand)[/dim]")


class OpcodeApp(App):

    CSS = """
    #chat {
        height: 1fr;
        overflow-y: auto;
        border: none;
        padding: 0 1;
    }
    .user-msg {
        margin: 1 0 0 0;
    }
    .assistant-msg {
        margin: 0 0 0 0;
    }
    .thinking-text {
        margin: 0 0 0 2;
        padding: 0 1;
        height: auto;
    }
    .thinking-toggle {
        margin: 0;
        padding: 0 1;
        height: 1;
        color: $text-disabled;
    }
    .hidden {
        display: none;
    }
    .tool-status {
        margin: 0 0 0 0;
    }
    #user-input {
        dock: bottom;
        margin: 0 1;
        border: solid $primary;
        height: auto;
        min-height: 3;
        max-height: 12;
    }
    """

    BINDINGS = [
        ("ctrl+x", "copy_response", "Copy last response"),
        ("ctrl+enter", "submit_input", "Send message"),
    ]

    def __init__(self, agent: Agent):
        super().__init__()
        self._agent = agent
        self._plan_pending = False
        self._last_response = ""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat", can_focus=False):
            yield Static("Welcome to opcode. Type /exit to quit.\nPress Ctrl+Enter to send, Ctrl+X to copy.")
        yield TextArea(id="user-input")

    def on_mount(self) -> None:
        self.query_one("#user-input", TextArea).focus()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self._agent.cancel()
            event.prevent_default()
            return

        inp = self.query_one("#user-input", TextArea)
        if not inp.has_focus and not inp.disabled and event.character:
            inp.focus()
            inp.insert(event.character)
            event.prevent_default()

    def action_copy_response(self) -> None:
        if self._last_response:
            self.copy_to_clipboard(self._last_response)
            self.notify("Copied to clipboard", timeout=2)

    def action_submit_input(self) -> None:
        inp = self.query_one("#user-input", TextArea)
        value = inp.text.strip()
        if not value:
            return
        inp.text = ""
        asyncio.ensure_future(self._process_input(value))

    async def _process_input(self, value: str) -> None:
        cmd = value.lower()
        inp = self.query_one("#user-input", TextArea)
        chat = self.query_one("#chat", VerticalScroll)

        if cmd in ("/exit", "/quit"):
            self.exit()
            return

        if cmd == "/copy":
            if self._last_response:
                self.copy_to_clipboard(self._last_response)
                self.notify("Copied to clipboard", timeout=2)
            else:
                self.notify("Nothing to copy", timeout=2)
            inp.focus()
            return

        if cmd == "/cancel":
            self._agent.cancel()
            inp.focus()
            return

        if cmd == "/plan":
            self._enter_plan_mode()
            await chat.mount(Static(
                "[dim]-- plan mode: read-only tools enabled, describe your task --[/dim]",
                classes="tool-status",
            ))
            chat.scroll_end(animate=False)
            inp.focus()
            return

        if cmd == "/do":
            self._enter_do_mode()
            await chat.mount(Static(
                "[dim]-- do mode: all tools enabled, executing plan --[/dim]",
                classes="tool-status",
            ))
            chat.scroll_end(animate=False)
            inp.focus()
            return

        inp.disabled = True

        await chat.mount(Static(f"[bold cyan]• {value}[/bold cyan]", classes="user-msg"))
        chat.scroll_end(animate=False)

        buf = ""
        thinking_buf = ""
        error_occurred = False
        tool_status_widgets: dict[str, Static] = {}

        assistant = Static("", classes="assistant-msg")
        await chat.mount(assistant)

        thinking_text = Static("", classes="thinking-text hidden")
        await chat.mount(thinking_text)
        thinking_toggle: ThinkingToggle | None = None

        chat.scroll_end(animate=False)

        def render() -> str:
            lines = ["[bold green]opcode[/bold green]"]
            if buf:
                lines.append(buf)
            return "\n".join(lines)

        try:
            async for agent_event in self._agent.run(value):
                if isinstance(agent_event, TextDelta):
                    buf += agent_event.content
                    assistant.update(render())
                elif isinstance(agent_event, ThinkingDelta):
                    thinking_buf += agent_event.content
                    thinking_text.update(f"[dim italic]{thinking_buf}[/dim italic]")
                    if thinking_toggle is None:
                        thinking_text.remove_class("hidden")
                        thinking_toggle = ThinkingToggle(thinking_text)
                        await chat.mount(thinking_toggle)
                elif isinstance(agent_event, ToolCallStart):
                    status = Static(
                        f"[dim]calling {agent_event.name}...[/dim]",
                        classes="tool-status",
                    )
                    tool_status_widgets[agent_event.tool_id] = status
                    await chat.mount(status)
                elif isinstance(agent_event, ToolCallInput):
                    pass
                elif isinstance(agent_event, ToolResultEvent):
                    w = tool_status_widgets.get(agent_event.tool_id)
                    if w is not None:
                        icon = "OK" if agent_event.result.success else "FAIL"
                        w.update(f"[dim]{icon} {agent_event.name}[/dim]")
                elif isinstance(agent_event, DoneEvent):
                    reason = agent_event.finish_reason
                    if reason == "cancelled":
                        if not buf:
                            assistant.update("[bold green]opcode[/bold green]\n[dim](cancelled)[/dim]")
                    elif reason == "max_iterations":
                        suffix = "\n[dim][max iterations reached][/dim]"
                        assistant.update(render() + suffix)
                    elif reason == "unknown_tool":
                        assistant.update("[bold green]opcode[/bold green]\n[bold red]Error: repeated unknown tool calls[/bold red]")
                    elif reason == "stream_error":
                        pass
                    elif agent_event.content:
                        assistant.update(f"[bold green]opcode[/bold green]\n{agent_event.content}")
                elif isinstance(agent_event, ErrorEvent):
                    assistant.update(f"[bold green]opcode[/bold green]\n[bold red]Error: {agent_event.message}[/bold red]")
                    error_occurred = True

                chat.scroll_end(animate=False)

        except Exception:
            assistant.update("[bold green]opcode[/bold green]\n[bold red]Error: unexpected error[/bold red]")
            error_occurred = True
        finally:
            if not buf and not thinking_buf and not error_occurred:
                assistant.update("[bold green]opcode[/bold green]\n[dim](no response)[/dim]")
            if thinking_buf and thinking_toggle is not None:
                thinking_toggle._expanded = False
                thinking_text.add_class("hidden")
                thinking_toggle.update("[dim][+] Thinking (click to expand)[/dim]")
            elif not thinking_buf:
                thinking_text.remove()
            self._last_response = buf
            inp.disabled = False
            inp.focus()

    def _enter_plan_mode(self) -> None:
        plan_mode = self._agent.plan_mode
        if plan_mode is None:
            return
        plan_mode.start_plan()
        self._plan_pending = True
        inp = self.query_one("#user-input", TextArea)
        inp.text = ""
        inp.border_title = "Describe your task for planning..."

    def _enter_do_mode(self) -> None:
        plan_mode = self._agent.plan_mode
        if plan_mode is None:
            return
        plan_mode.start_do()
        self._plan_pending = False
        inp = self.query_one("#user-input", TextArea)
        inp.text = ""
        inp.border_title = "Executing plan..."
