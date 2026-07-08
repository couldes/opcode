from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass

_ALIASES: dict[str, str] = {
    "bash": "run_command",
    "read": "read_file",
    "write": "write_file",
    "edit": "edit_file",
    "glob": "glob_find",
    "grep": "grep_search",
    "readfile": "read_file",
    "writefile": "write_file",
    "editfile": "edit_file",
    "runcommand": "run_command",
    "globfind": "glob_find",
    "grepsearch": "grep_search",
}


def _camel_to_snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _resolve_tool_name(name: str) -> str:
    lower = name.lower()
    if lower in _ALIASES:
        return _ALIASES[lower]
    snake = _camel_to_snake(name)
    if snake in _ALIASES:
        return _ALIASES[snake]
    return snake


def _serialize_args(input: dict) -> str:
    for key in ("command", "path", "pattern"):
        if key in input:
            return str(input[key])
    values = [str(v) for v in input.values()]
    return " ".join(values)


@dataclass
class Rule:
    tool_name: str
    pattern: str
    action: str  # "allow" | "deny"


class RuleSet:

    def __init__(self) -> None:
        self._rules: list[Rule] = []

    def add(self, rule: Rule) -> None:
        self._rules.append(rule)

    def match(self, tool_name: str, args_str: str) -> str | None:
        for rule in self._rules:
            if tool_name != rule.tool_name:
                continue
            if fnmatch.fnmatch(args_str, rule.pattern):
                return rule.action
        return None


def parse_rule_spec(spec: str, action: str) -> Rule:
    spec = spec.strip()
    if "(" not in spec or not spec.endswith(")"):
        raise ValueError(f"invalid rule format: '{spec}'")
    tool_part, pattern_part = spec.split("(", 1)
    pattern_part = pattern_part[:-1]
    tool_name = _resolve_tool_name(tool_part.strip())
    pattern = pattern_part.strip() or "*"
    if action not in ("allow", "deny"):
        raise ValueError(f"invalid action: '{action}'")
    return Rule(tool_name=tool_name, pattern=pattern, action=action)
