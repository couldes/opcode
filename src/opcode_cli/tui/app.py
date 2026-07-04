from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Input, Static

from opcode_cli.controller import ChatController
from opcode_cli.provider.base import StreamChunk


class OpcodeApp(App):

    ENABLE_MOUSE_CAPTURE = False

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
    .tool-status {
        margin: 0 0 0 0;
    }
    #user-input {
        dock: bottom;
        margin: 0 1;
        border: solid $primary;
    }
    """

    def __init__(self, controller: ChatController):
        super().__init__()
        self._controller = controller
        self._tool_status: Static | None = None

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="chat", can_focus=False):
            yield Static("Welcome to opcode. Type /exit to quit.")
        yield Input(id="user-input", placeholder="Type a message... (/exit to quit)")

    def on_mount(self) -> None:
        self.query_one("#user-input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return

        cmd = value.lower()
        if cmd in ("/exit", "/quit"):
            self.exit()
            return

        inp = self.query_one("#user-input", Input)
        chat = self.query_one("#chat", VerticalScroll)

        inp.disabled = True

        await chat.mount(Static(f"[bold cyan]> {value}[/bold cyan]", classes="user-msg"))
        chat.scroll_end(animate=False)

        buf = ""
        thinking_buf = ""
        has_content = False

        assistant = Static("", classes="assistant-msg")
        await chat.mount(assistant)
        chat.scroll_end(animate=False)

        def render() -> str:
            lines = ["[bold green]┃ opcode[/bold green]"]
            if thinking_buf:
                lines.append(f"[dim italic]{thinking_buf}[/dim italic]")
            if buf:
                lines.append(buf)
            return "\n".join(lines)

        async def on_chunk(chunk: StreamChunk) -> None:
            nonlocal buf, thinking_buf, has_content
            if chunk.content:
                has_content = True
                buf += chunk.content
            if chunk.thinking:
                thinking_buf += chunk.thinking
            assistant.update(render())
            chat.scroll_end(animate=False)

        async def on_tool_call(*args) -> None:
            nonlocal has_content
            if len(args) == 2:
                name, input_dict = args
                has_content = True
                args_str = ", ".join(
                    f"{k}={repr(v)[:40]}" for k, v in input_dict.items()
                )
                self._tool_status = Static(
                    f"[dim]calling {name}({args_str})...[/dim]",
                    classes="tool-status",
                )
                await chat.mount(self._tool_status)
            elif len(args) == 3:
                name, _input_dict, result = args
                if self._tool_status is not None:
                    icon = "OK" if result.success else "FAIL"
                    self._tool_status.update(f"[dim]{icon} {name}[/dim]")
            chat.scroll_end(animate=False)

        try:
            await self._controller.send(value, on_chunk, on_tool_call)
        except Exception:
            assistant.update("[bold red]Error: unexpected error[/bold red]")
        finally:
            if not has_content and not thinking_buf:
                assistant.update(
                    f"[bold green]┃ opcode[/bold green]\n[dim](no response)[/dim]"
                )
            inp.clear()
            inp.disabled = False
            inp.focus()
