import asyncio
import sys

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static, TextArea

from pathlib import Path

from opcode_cli.agent.agent import Agent
from opcode_cli.commands import CommandRegistry, dispatch, get_completions, parse
from opcode_cli.agent.events import (
    CompressionSkippedEvent,
    DoneEvent,
    ErrorEvent,
    OffloadEvent,
    PermissionPromptEvent,
    SummarizeEvent,
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


class ChatInput(TextArea):
    """Enter 提交，Shift+Enter 换行。"""

    BINDINGS = [
        ("shift+enter", "insert_newline", "New line"),
    ]

    async def _on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()
            action_submit = getattr(self.app, "action_submit_input", None)
            if action_submit is not None:
                action_submit()
            return
        if event.key == "tab":
            text = self.text
            if text.startswith("/"):
                event.stop()
                event.prevent_default()
                handler = getattr(self.app, "handle_tab_completion", None)
                if handler is not None:
                    handler(text, self.cursor_location)
                return
        await super()._on_key(event)

    def action_insert_newline(self) -> None:
        self.insert("\n")


class StatusBar(Static):
    """显示当前模式标记：[DEFAULT] / [PLAN]"""

    def __init__(self) -> None:
        super().__init__("[reverse] DEFAULT [/reverse]", id="status-bar")


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
    #status-bar {
        dock: bottom;
        height: 1;
        margin: 0 1;
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
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+x", "copy_response", "Copy last response"),
        ("enter", "submit_input", "Send"),
    ]

    def __init__(self, agent: Agent, command_registry: CommandRegistry | None = None):
        super().__init__()
        self._agent = agent
        self._command_registry = command_registry
        self._plan_pending = False
        self._last_response = ""
        self._permission_decision_event: asyncio.Event | None = None
        self._permission_decision: str = ""
        self._waiting_permission = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat", can_focus=False):
            yield Static("Welcome to opcode. Type /help for commands, /exit to quit.\nPress Enter to send, Shift+Enter for new line.")
        yield StatusBar()
        yield ChatInput(id="user-input")

    def on_mount(self) -> None:
        self.query_one("#user-input", ChatInput).focus()

    def _on_key(self, event) -> None:
        if event.key == "escape":
            self._agent.cancel()
            event.stop()
            return

        if getattr(self, "_waiting_permission", False):
            key = event.key.lower()
            if key == "y":
                self._permission_decision = "allow_once"
                if self._permission_decision_event:
                    self._permission_decision_event.set()
                event.stop()
                return
            elif key == "s":
                self._permission_decision = "allow_session"
                if self._permission_decision_event:
                    self._permission_decision_event.set()
                event.stop()
                return
            elif key == "n":
                self._permission_decision = "deny"
                if self._permission_decision_event:
                    self._permission_decision_event.set()
                event.stop()
                return

        inp = self.query_one("#user-input", ChatInput)
        if not inp.has_focus and not inp.disabled and event.character:
            inp.focus()
            inp.insert(event.character)
            event.stop()

    def action_copy_response(self) -> None:
        if self._last_response:
            self.copy_to_clipboard(self._last_response)
            self.notify("Copied to clipboard", timeout=2)

    def action_submit_input(self) -> None:
        inp = self.query_one("#user-input", ChatInput)
        value = inp.text.strip()
        if not value:
            return
        inp.text = ""
        asyncio.ensure_future(self._process_input(value))

    def _update_status_bar(self) -> None:
        mode = self.get_mode()
        try:
            bar = self.query_one("#status-bar", Static)
            bar.update(f"[reverse] {mode} [/reverse]")
        except Exception:
            pass

    def handle_tab_completion(self, text: str, cursor_pos: tuple[int, int]) -> None:
        if self._command_registry is None:
            return
        col = cursor_pos[1]
        after_slash = text[1:col].lower()
        if " " in after_slash:
            return

        matches = get_completions(after_slash, self._command_registry)
        chat = self.query_one("#chat", VerticalScroll)
        inp = self.query_one("#user-input", ChatInput)

        if len(matches) == 1:
            rest = text[col:]
            inp.text = f"/{matches[0]} {rest}"
            inp.cursor_location = (0, len(matches[0]) + 2)
        elif len(matches) > 1:
            names = "  ".join(f"/{m}" for m in matches)
            asyncio.ensure_future(
                chat.mount(Static(f"[dim]{names}[/dim]", classes="tool-status"))
            )
            asyncio.ensure_future(chat.scroll_end(animate=False))

    def get_mode(self) -> str:
        plan_mode = self._agent.plan_mode
        if plan_mode and plan_mode.in_plan:
            return "PLAN"
        return "DEFAULT"

    async def _cleanup_mcp(self) -> None:
        """关闭 MCP 连接，避免退出时报 async generator 错误。"""
        mcp_manager = getattr(self._agent, "_mcp_manager", None)
        if mcp_manager is not None:
            try:
                await mcp_manager.disconnect_all()
            except Exception:
                pass

    def _on_exit_app(self) -> None:
        """Ctrl+C 退出时清理 MCP 资源。"""
        mcp_manager = getattr(self._agent, "_mcp_manager", None)
        if mcp_manager is not None:
            try:
                asyncio.ensure_future(mcp_manager.disconnect_all())
            except Exception:
                pass

    async def _process_input(self, value: str) -> None:
        cmd_lower = value.lower().strip()
        inp = self.query_one("#user-input", ChatInput)

        # 系统外前置命令（不在 registry 中）
        if cmd_lower in ("/exit", "/quit"):
            await self._cleanup_mcp()
            self.exit()
            return

        if cmd_lower == "/cancel":
            self._agent.cancel()
            inp.focus()
            return

        if cmd_lower == "/copy":
            if self._last_response:
                self.copy_to_clipboard(self._last_response)
                self.notify("Copied to clipboard", timeout=2)
            else:
                self.notify("Nothing to copy", timeout=2)
            inp.focus()
            return

        # 命令分流：命中 → 本地分发
        if self._command_registry is not None:
            parsed = parse(value, self._command_registry)
            if parsed is not None:
                await dispatch(parsed, self)
                inp.focus()
                return

        # 不是命令 → 送入 Agent
        await self._process_agent_input(value)

    async def _process_agent_input(self, value: str) -> None:
        inp = self.query_one("#user-input", ChatInput)
        chat = self.query_one("#chat", VerticalScroll)
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
                elif isinstance(agent_event, PermissionPromptEvent):
                    if not sys.stdin.isatty():
                        self._agent.respond_to_permission("deny")
                        continue
                    prompt = Static(
                        f"[bold yellow][?][/bold yellow] Allow {agent_event.tool_name}({agent_event.args_str})? "
                        "[bold](y)[/bold]es this time / [bold](s)[/bold]ession / [bold](n)[/bold]o",
                        classes="tool-status",
                    )
                    await chat.mount(prompt)
                    chat.scroll_end(animate=False)
                    inp.blur()
                    decision = await self._wait_for_permission_choice()
                    inp.focus()
                    await prompt.remove()
                    self._agent.respond_to_permission(decision)
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
                elif isinstance(agent_event, OffloadEvent):
                    await chat.mount(Static(
                        f"[dim]Offloaded {agent_event.count} tool results to disk[/dim]",
                        classes="tool-status",
                    ))
                elif isinstance(agent_event, SummarizeEvent):
                    await chat.mount(Static(
                        f"[dim]Summarized {agent_event.summarized_count} messages "
                        f"({agent_event.total_before // 1000}K -> {agent_event.total_after // 1000}K tokens)[/dim]",
                        classes="tool-status",
                    ))
                elif isinstance(agent_event, CompressionSkippedEvent):
                    if agent_event.reason == "broken":
                        await chat.mount(Static(
                            "[dim]Compression skipped: summarizer broken[/dim]",
                            classes="tool-status",
                        ))
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

    async def _wait_for_permission_choice(self) -> str:
        self._permission_decision_event = asyncio.Event()
        self._permission_decision = ""
        self._waiting_permission = True
        try:
            await asyncio.wait_for(
                self._permission_decision_event.wait(),
                timeout=60.0,
            )
        except asyncio.TimeoutError:
            self._permission_decision = "deny"
        self._waiting_permission = False
        self._permission_decision_event = None
        return self._permission_decision

    # --- UiController implementation ---

    async def display_message(self, text: str) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        await chat.mount(Static(text, classes="tool-status"))
        chat.scroll_end(animate=False)

    async def send_to_agent(self, text: str) -> None:
        await self._process_agent_input(text)

    def switch_mode(self, mode: str) -> None:
        if mode == "plan":
            self._enter_plan_mode()
        elif mode in ("default", "do"):
            self._enter_do_mode()
        self._update_status_bar()

    def get_token_usage(self) -> dict | None:
        tracker = self._agent.tracker
        s = tracker.summary
        if not s or s.get("input_tokens", 0) == 0:
            return None
        return dict(s)

    def get_session_id(self) -> str:
        archiver = getattr(self._agent, "_archiver", None)
        if archiver:
            return archiver._session_id
        return "unknown"

    async def refresh_status(self) -> None:
        self._update_status_bar()

    async def clear_chat(self) -> None:
        if self._agent._skills_manager:
            self._agent._skills_manager.clear()
        old = self.query_one("#chat", VerticalScroll)
        await old.remove()
        new_chat = VerticalScroll(id="chat", can_focus=False)
        await self.mount(new_chat, before=self.query_one("#status-bar"))
        await new_chat.mount(
            Static("Chat cleared. Type /help for commands, /exit to quit.")
        )

    def _enter_plan_mode(self) -> None:
        plan_mode = self._agent.plan_mode
        if plan_mode is None:
            return
        plan_mode.start_plan()
        self._plan_pending = True
        inp = self.query_one("#user-input", ChatInput)
        inp.text = ""
        inp.border_title = "Describe your task for planning..."
        self._update_status_bar()

    def _enter_do_mode(self) -> None:
        plan_mode = self._agent.plan_mode
        if plan_mode is None:
            return
        plan_mode.start_do()
        self._plan_pending = False
        inp = self.query_one("#user-input", ChatInput)
        inp.text = ""
        inp.border_title = "Executing plan..."
        self._update_status_bar()
