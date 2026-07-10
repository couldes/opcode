from __future__ import annotations

from dataclasses import dataclass

from opcode_cli.commands.registry import Command, CommandRegistry


@dataclass
class ParsedCommand:
    command: Command
    args: str


def parse(user_input: str, registry: CommandRegistry) -> ParsedCommand | None:
    text = user_input.strip()
    if not text.startswith("/"):
        return None

    after_slash = text[1:]
    if not after_slash:
        return None

    if " " in after_slash:
        cmd_name, args = after_slash.split(" ", 1)
    else:
        cmd_name = after_slash
        args = ""

    cmd = registry.get(cmd_name)
    if cmd is None:
        return None

    return ParsedCommand(command=cmd, args=args)
