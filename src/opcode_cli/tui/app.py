from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Input, RichLog

from opcode_cli.controller import ChatController
from opcode_cli.provider.base import StreamChunk


class OpcodeApp(App):

    CSS = """
    #history {
        height: 1fr;
        border: none;
    }
    #streaming {
        height: auto;
        max-height: 40%;
        border: none;
    }
    #user-input {
        dock: bottom;
        border: solid $primary;
    }
    """

    def __init__(self, controller: ChatController):
        super().__init__()
        self._controller = controller

    def compose(self) -> ComposeResult:
        with Container():
            yield RichLog(id="history", highlight=True, markup=True, wrap=True)
            yield RichLog(id="streaming", highlight=True, markup=True, wrap=True)
            yield Input(id="user-input", placeholder="Type your message... (/exit to quit)")

    def on_mount(self) -> None:
        self.query_one("#history", RichLog).write(
            "Welcome to opcode. Type /exit to quit.", animate=False
        )
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
        history = self.query_one("#history", RichLog)
        streaming = self.query_one("#streaming", RichLog)

        inp.disabled = True
        history.write(f"[bold]You:[/bold] {value}")

        content_buf = ""
        thinking_buf = ""

        def render_streaming() -> None:
            streaming.clear()
            if thinking_buf:
                streaming.write(f"[dim italic]{thinking_buf}[/dim italic]")
            if content_buf:
                streaming.write(content_buf)

        async def on_chunk(chunk: StreamChunk) -> None:
            nonlocal content_buf, thinking_buf
            if chunk.content:
                content_buf += chunk.content
                render_streaming()
            if chunk.thinking:
                thinking_buf += chunk.thinking
                render_streaming()

        try:
            await self._controller.send(value, on_chunk)
        finally:
            if content_buf:
                history.write(f"[bold]Assistant:[/bold] {content_buf}")
            elif thinking_buf:
                history.write(f"[bold]Assistant:[/bold] [dim italic](thinking only)[/dim italic]")
            else:
                history.write("[bold]Assistant:[/bold] [dim](no response)[/dim]")
            streaming.clear()
            inp.clear()
            inp.disabled = False
            inp.focus()
