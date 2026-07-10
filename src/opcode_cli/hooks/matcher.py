from __future__ import annotations

import fnmatch
import re

from opcode_cli.hooks.types import HookCondition


def _resolve_field(data: dict, path: str) -> str:
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    if isinstance(current, str):
        return current
    return str(current)


def _match_pattern(value: str, pattern: str) -> bool:
    if len(pattern) >= 2 and pattern.startswith("/") and pattern.endswith("/"):
        inner = pattern[1:-1]
        return bool(re.search(inner, value))
    if pattern.startswith("!"):
        rest = pattern[1:]
        return not fnmatch.fnmatch(value, rest)
    return fnmatch.fnmatch(value, pattern)


def match_condition(
    condition: HookCondition | None, context_data: dict
) -> bool:
    if condition is None:
        return True
    if not condition.match:
        return True

    results = []
    for field_path, pattern in condition.match.items():
        value = _resolve_field(context_data, field_path)
        results.append(_match_pattern(value, pattern))

    if condition.mode == "any":
        return any(results)
    return all(results)
