import asyncio
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll

from opcode_cli.agent.agent import Agent
from opcode_cli.commands import CommandRegistry, dispatch, get_completions, parse
from opcode_cli.tui.timeline import TimelineRenderer
from opcode_cli.tui.widgets import (
    NotificationNode,
    StatusBar,
    UserMsgNode,
)
from opcode_cli.tui.widgets.chat_input import OpcodeChatInput


class OpcodeApp(App):

    AUTO_FOCUS = "#user-input"
    CSS_PATH = "styles.tcss"

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

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat", can_focus=False):
            yield UserMsgNode("[bold green]Welcome to opcode.[/bold green]\nType /help for commands, /exit to quit.")
        yield StatusBar()
        yield OpcodeChatInput(work_dir=str(Path.cwd()), id="user-input")

    def on_mount(self) -> None:
        self._focus_input()
        # Belt-and-suspenders: AUTO_FOCUS only activates after first keypress
        # (app_focus becomes True). Defer a second focus attempt until after
        # the initial render so focus survives timing variations.
        self.call_after_refresh(self._focus_input)

    def _focus_input(self) -> None:
        try:
            inp = self.query_one("#user-input", OpcodeChatInput)
            inp.focus()
            inp.scroll_visible(animate=False)
        except Exception:
            pass

    async def _on_key(self, event) -> None:
        if event.key == "escape":
            self._agent.cancel()
            event.stop()
            return

        if event.is_printable:
            try:
                inp = self.query_one("#user-input", OpcodeChatInput)
                if not inp.has_focus and not inp.disabled:
                    inp.focus()
                    inp.insert(event.character)
                    event.stop()
                    return
            except Exception:
                pass

        # Do NOT call super()._on_key(event) here.
        # Textual's _get_dispatch_methods yields both OpcodeApp._on_key
        # and App._on_key from the MRO, and _on_message calls BOTH.
        # Calling super() would trigger the default _on_key a second time,
        # causing _check_bindings to fire twice per keypress.

    def action_copy_response(self) -> None:
        if self._last_response:
            self.copy_to_clipboard(self._last_response)
            self.notify("Copied to clipboard", timeout=2)

    def action_submit_input(self) -> None:
        inp = self.query_one("#user-input", OpcodeChatInput)
        value = inp.text.strip()
        if not value:
            return
        inp.text = ""
        asyncio.ensure_future(self._process_input(value))

    def _update_status_bar(self) -> None:
        mode = self.get_mode()
        try:
            bar = self.query_one("#status-bar", StatusBar)
            bar.update_mode(mode)
            usage = self.get_token_usage()
            if usage:
                bar.update_tokens(usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
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
        inp = self.query_one("#user-input", OpcodeChatInput)

        if len(matches) == 1:
            rest = text[col:]
            inp.text = f"/{matches[0]} {rest}"
            inp.cursor_location = (0, len(matches[0]) + 2)
        elif len(matches) > 1:
            names = "  ".join(f"/{m}" for m in matches)
            asyncio.ensure_future(
                chat.mount(NotificationNode(names))
            )
            asyncio.ensure_future(chat.scroll_end(animate=False))

    def get_mode(self) -> str:
        plan_mode = self._agent.plan_mode
        if plan_mode and plan_mode.in_plan:
            return "PLAN"
        return "DEFAULT"

    async def _cleanup_mcp(self) -> None:
        mcp_manager = getattr(self._agent, "_mcp_manager", None)
        if mcp_manager is not None:
            try:
                await mcp_manager.disconnect_all()
            except Exception:
                pass

    def _on_exit_app(self) -> None:
        mcp_manager = getattr(self._agent, "_mcp_manager", None)
        if mcp_manager is not None:
            try:
                asyncio.ensure_future(mcp_manager.disconnect_all())
            except Exception:
                pass

    async def _process_input(self, value: str) -> None:
        cmd_lower = value.lower().strip()
        inp = self.query_one("#user-input", OpcodeChatInput)

        # --- Handle pending permission (y/s/d/n typed in the input box) ---
        perm = getattr(inp, "_pending_permission", None)
        if perm is not None and not perm.is_done:
            if perm.resolve(cmd_lower):
                inp._pending_permission = None
                inp.text = ""
                inp.disabled = True  # re-lock while agent continues
                return
            # Invalid key — clear the input so the user can retry
            inp.text = ""
            inp.focus()
            return

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

        if self._command_registry is not None:
            parsed = parse(value, self._command_registry)
            if parsed is not None:
                await dispatch(parsed, self)
                inp.focus()
                return

        await self._process_agent_input(value)

    async def _process_agent_input(self, value: str) -> None:
        inp = self.query_one("#user-input", OpcodeChatInput)
        chat = self.query_one("#chat", VerticalScroll)
        inp.disabled = True
        # Clear stray content inserted by TextArea._on_key dispatch after our
        # Enter handler already cleared the text (double-dispatch side effect).
        inp.text = ""

        await chat.mount(UserMsgNode(value))
        chat.scroll_end(animate=False)

        renderer = TimelineRenderer(chat, input_widget=inp)

        try:
            await renderer.render(self._agent.run(value))
        except Exception:
            await chat.mount(
                NotificationNode("[red]Error: unexpected error[/red]")
            )
        finally:
            self._last_response = renderer._buf
            inp.disabled = False
            inp.focus()
            chat.scroll_end(animate=False)
            self._update_status_bar()

    # --- UiController implementation ---

    async def display_message(self, text: str) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        await chat.mount(NotificationNode(text))
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
            NotificationNode("Chat cleared. Type /help for commands, /exit to quit.")
        )

    def _enter_plan_mode(self) -> None:
        plan_mode = self._agent.plan_mode
        if plan_mode is None:
            return
        plan_mode.start_plan()
        self._plan_pending = True
        inp = self.query_one("#user-input", OpcodeChatInput)
        inp.text = ""
        inp.border_title = "Describe your task for planning..."
        self._update_status_bar()

    def _enter_do_mode(self) -> None:
        plan_mode = self._agent.plan_mode
        if plan_mode is None:
            return
        plan_mode.start_do()
        self._plan_pending = False
        inp = self.query_one("#user-input", OpcodeChatInput)
        inp.text = ""
        inp.border_title = "Executing plan..."
        self._update_status_bar()
