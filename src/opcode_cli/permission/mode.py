from enum import Enum


class PermissionMode(Enum):
    STRICT = "strict"
    DEFAULT = "default"
    ACCEPT_EDITS = "accept-edits"
    PERMISSIVE = "permissive"


_READ_ONLY_TOOLS = {"read_file", "glob_find", "grep_search"}


def mode_fallback(mode: PermissionMode, tool_name: str) -> str:
    if mode == PermissionMode.STRICT:
        return "deny"
    if mode == PermissionMode.PERMISSIVE:
        return "allow"
    if mode == PermissionMode.ACCEPT_EDITS:
        if tool_name == "run_command":
            return "ask_user"
        return "allow"
    return "allow" if tool_name in _READ_ONLY_TOOLS else "ask_user"
