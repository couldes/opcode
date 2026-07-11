from __future__ import annotations

from opcode_cli.commands.context import CommandContext
from opcode_cli.commands.registry import Command


_REVIEW_PROMPT = """You are in code review mode.

Review the following code or changes. Check for:
- Correctness: does it work as intended?
- Edge cases: what happens with empty/null/unexpected input?
- Consistency: does it follow existing patterns?
- Security: are there injection or validation issues?
- Testability: can each change be verified?

Focus on {focus}."""


def make_review_command(deps: CommandContext) -> Command:
    def handler(args: str) -> str:
        if args.strip():
            focus = args.strip()
            return _REVIEW_PROMPT.format(focus=focus)
        return (
            "Review mode. Usage: /review <focus-area>\n"
            "Example: /review security\n\n"
            "Available focus areas: security, performance, correctness, style, architecture"
        )

    return Command(
        name="review",
        aliases=[],
        description="Switch to review mode with optional focus area",
        usage="/review [focus]",
        cmd_type="prompt",
        arg_hint="[focus]",
        hidden=False,
        handler=handler,
    )
