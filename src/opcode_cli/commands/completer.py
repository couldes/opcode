from __future__ import annotations

from opcode_cli.commands.registry import CommandRegistry


def get_completions(prefix: str, registry: CommandRegistry) -> list[str]:
    key = prefix.lower()
    return sorted(
        [n for n in registry.get_matchable_names() if n.startswith(key)]
    )
