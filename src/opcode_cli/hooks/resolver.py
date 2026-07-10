from __future__ import annotations

import re

from opcode_cli.hooks.types import HookContext

_PLACEHOLDER_RE = re.compile(r"\{\{(.+?)\}\}")


def _resolve_value(data: dict, path: str) -> str:
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


def resolve_placeholders(
    template: str | None, context: HookContext
) -> str | None:
    if template is None:
        return None

    def _replace(match: re.Match) -> str:
        path = match.group(1).strip()
        # Try context.data first
        value = _resolve_value(context.data, path)
        if value != "":
            return value
        # Try top-level context fields
        if path == "event":
            return context.event
        if path == "session_id":
            return context.session_id
        if path == "project_root":
            return context.project_root
        if path == "timestamp":
            return str(context.timestamp)
        return match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, template)


def resolve_dict(obj: dict, context: HookContext) -> dict:
    result = {}
    for key, value in obj.items():
        if isinstance(value, str):
            result[key] = resolve_placeholders(value, context)
        elif isinstance(value, dict):
            result[key] = resolve_dict(value, context)
        else:
            result[key] = value
    return result
