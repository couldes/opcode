from __future__ import annotations

from opcode_cli.commands.controller import UiController
from opcode_cli.commands.parser import ParsedCommand


async def dispatch(parsed: ParsedCommand, ui: UiController) -> None:
    cmd = parsed.command
    if cmd.cmd_type == "local":
        result = cmd.handler(parsed.args)
        await ui.display_message(result)
    elif cmd.cmd_type == "ui":
        await cmd.handler(parsed.args, ui)
    elif cmd.cmd_type == "prompt":
        prompt = cmd.handler(parsed.args)
        await ui.send_to_agent(prompt)
