from __future__ import annotations

from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.controller import UiController
from opcode_cli.commands.registry import Command


def make_plan_command(deps: CommandDeps) -> Command:
    async def handler(args: str, ui: UiController) -> None:
        ui.switch_mode("plan")
        await ui.display_message(
            "[dim]-- plan mode: read-only tools enabled, describe your task --[/dim]"
        )

    return Command(
        name="plan",
        aliases=["p"],
        description="Enter Plan Mode (read-only exploration)",
        usage="/plan",
        cmd_type="ui",
        arg_hint=None,
        hidden=False,
        handler=handler,
    )
