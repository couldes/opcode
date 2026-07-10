from __future__ import annotations

from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.registry import Command


def make_help_command(deps: CommandDeps) -> Command:
    def handler(args: str) -> str:
        cmds = deps.command_registry.list_visible()
        lines = ["Commands:"]
        for c in cmds:
            alias_hint = ""
            if c.aliases:
                alias_hint = f" (alias: /{' /'.join(c.aliases)})"
            lines.append(f"  /{c.name:<14} {c.description}{alias_hint}")
        lines.append("")
        lines.append("Type /<command> --help for detailed usage.")
        return "\n".join(lines)

    return Command(
        name="help",
        aliases=["?", "h"],
        description="Show this help message",
        usage="/help",
        cmd_type="local",
        arg_hint=None,
        hidden=False,
        handler=handler,
    )
