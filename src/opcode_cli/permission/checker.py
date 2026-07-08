from __future__ import annotations

from opcode_cli.permission.blacklist import check_command
from opcode_cli.permission.mode import PermissionMode, mode_fallback
from opcode_cli.permission.rules import Rule, RuleSet, _serialize_args
from opcode_cli.permission.sandbox import check_path
from opcode_cli.provider.base import ToolCall

_FILE_TOOLS = {"read_file", "write_file", "edit_file", "glob_find", "grep_search"}


class PermissionChecker:

    def __init__(
        self,
        project_root: str,
        mode: PermissionMode,
        base_rules: RuleSet | None = None,
        session_rules: RuleSet | None = None,
        registry: object | None = None,
    ) -> None:
        self._project_root = project_root
        self._mode = mode
        self._base_rules = base_rules or RuleSet()
        self._session_rules = session_rules or RuleSet()
        self._registry = registry

    def check(self, tool_call: ToolCall) -> str:
        """Run L1→L4 checks. Returns 'allow', 'deny', or 'ask_user'."""
        tool_name = tool_call.name
        tool_input = tool_call.input

        # L1: blacklist (run_command only)
        if tool_name == "run_command" and "command" in tool_input:
            blocked, reason = check_command(str(tool_input["command"]))
            if blocked:
                return "deny"

        # L2: sandbox (file tools only)
        if tool_name in _FILE_TOOLS:
            path_key = (
                "path" if "path" in tool_input
                else "pattern" if "pattern" in tool_input
                else None
            )
            if path_key:
                allowed, _ = check_path(
                    str(tool_input[path_key]),
                    self._project_root,
                )
                if not allowed:
                    return "deny"

        # L3: rule engine (session rules first, then base rules)
        args_str = _serialize_args(tool_input)
        result = self._session_rules.match(tool_name, args_str)
        if result is not None:
            return result
        result = self._base_rules.match(tool_name, args_str)
        if result is not None:
            return result

        # L3.5: read-only tools auto-allow
        if self._registry is not None:
            try:
                tool = self._registry.get(tool_name)
                if tool.read_only:
                    return "allow"
            except KeyError:
                pass

        # L4: mode fallback
        return mode_fallback(self._mode, tool_name)

    def add_session_rule(self, rule: Rule) -> None:
        self._session_rules.add(rule)
