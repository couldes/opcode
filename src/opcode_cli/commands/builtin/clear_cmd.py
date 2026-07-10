from __future__ import annotations

from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.controller import UiController
from opcode_cli.commands.registry import Command


def make_clear_command(deps: CommandDeps) -> Command:
    async def handler(args: str, ui: UiController) -> None:
        await ui.clear_chat()

    return Command(
        name="clear",
        aliases=["cls"],
        description="Clear the chat area",
        usage="/clear",
        cmd_type="ui",
        arg_hint=None,
        hidden=False,
        handler=handler,
    )
