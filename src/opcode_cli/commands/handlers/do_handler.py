from __future__ import annotations

from opcode_cli.commands.context import CommandContext
from opcode_cli.commands.controller import UiController
from opcode_cli.commands.registry import Command


def make_do_command(deps: CommandContext) -> Command:
    async def handler(args: str, ui: UiController) -> None:
        ui.switch_mode("default")
        await ui.display_message(
            "[dim]-- do mode: all tools enabled, executing plan --[/dim]"
        )

    return Command(
        name="do",
        aliases=["d"],
        description="Exit Plan Mode and execute the plan",
        usage="/do",
        cmd_type="ui",
        arg_hint=None,
        hidden=False,
        handler=handler,
    )
