from __future__ import annotations

from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.registry import Command


def make_review_command(deps: CommandDeps) -> Command:
    def handler(args: str) -> str:
        base = (
            "Review the current code changes in this project for potential issues."
        )
        if args.strip():
            return f"{base} Focus on {args.strip()}."
        return base

    return Command(
        name="review",
        aliases=[],
        description="Submit current changes for code review",
        usage="/review [focus]",
        cmd_type="prompt",
        arg_hint="focus area",
        hidden=False,
        handler=handler,
    )
