from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, Literal

LocalHandler = Callable[[str], str]
UiHandler = Callable[[str, "UiController"], Coroutine[Any, Any, None]]
PromptHandler = Callable[[str], str]


@dataclass
class Command:
    name: str
    description: str
    usage: str
    cmd_type: Literal["local", "ui", "prompt"]
    handler: LocalHandler | UiHandler | PromptHandler
    aliases: list[str] = field(default_factory=list)
    arg_hint: str | None = None
    hidden: bool = False


class CommandConflictError(Exception):
    pass


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._alias_to_name: dict[str, str] = {}

    def register(self, cmd: Command) -> None:
        all_names = {cmd.name, *cmd.aliases}
        existing = set(self._commands.keys()) | set(self._alias_to_name.keys())
        conflict = all_names & existing
        if conflict:
            raise CommandConflictError(
                f"command '{cmd.name}': names/aliases already registered: {conflict}"
            )
        self._commands[cmd.name] = cmd
        for alias in cmd.aliases:
            self._alias_to_name[alias] = cmd.name

    def get(self, name_or_alias: str) -> Command | None:
        key = name_or_alias.lower()
        if key in self._commands:
            return self._commands[key]
        name = self._alias_to_name.get(key)
        if name:
            return self._commands.get(name)
        return None

    def list_visible(self) -> list[Command]:
        return sorted(
            [c for c in self._commands.values() if not c.hidden],
            key=lambda c: c.name,
        )

    def get_matchable_names(self) -> set[str]:
        result: set[str] = set()
        for cmd in self._commands.values():
            if not cmd.hidden:
                result.add(cmd.name)
                result.update(cmd.aliases)
        return result
