from __future__ import annotations

from opcode_cli.permission.dangerous import DangerousCommandDetector
from opcode_cli.permission.mode import PermissionMode, mode_fallback
from opcode_cli.permission.rules import Rule, RuleSet, _serialize_args
from opcode_cli.permission.sandbox import check_path
from opcode_cli.provider.base import ToolCall

_FILE_TOOLS = {"read_file", "write_file", "edit_file", "glob_find", "grep_search"}


class PermissionChecker:
    """9-layer permission decision chain.

    Layer | Name              | Effect
    ------|-------------------|-------
    0     | Plan mode         | Auto-allow when plan mode is active
    1     | Read-only         | Auto-allow tools marked is_read_only
    1b    | Danger blacklist  | Block dangerous shell commands
    1c    | OS sandbox        | Auto-allow when OS sandbox is active (future)
    2     | Path sandbox      | Block file access outside project root
    3     | Rule engine       | Match session rules, then base rules
    3.5   | Session allow     | "Don't ask again" set (exact match)
    4     | Mode fallback     | Mode matrix decision
    5     | HITL              | Handled by agent.py when L4 returns "ask_user"
    """

    def __init__(
        self,
        project_root: str,
        mode: PermissionMode,
        base_rules: RuleSet | None = None,
        session_rules: RuleSet | None = None,
        registry: object | None = None,
        dangerous_detector: DangerousCommandDetector | None = None,
        plan_mode: object | None = None,
    ) -> None:
        self._project_root = project_root
        self._mode = mode
        self._base_rules = base_rules or RuleSet()
        self._session_rules = session_rules or RuleSet()
        self._registry = registry
        self._dangerous_detector = dangerous_detector or DangerousCommandDetector()
        self._plan_mode = plan_mode
        # Layer 3.5: session-level "don't ask again" set (in-memory, exact match)
        self._session_allow_set: set[tuple[str, str]] = set()

    def add_session_rule(self, rule: Rule) -> None:
        self._session_rules.add(rule)

    def add_session_allow(self, tool_name: str, args_str: str) -> None:
        """Add (tool, args) to the Layer 3.5 "don't ask again" set."""
        self._session_allow_set.add((tool_name, args_str))

    def check(self, tool_call: ToolCall) -> str:
        """Run 9-layer decision chain. Returns 'allow', 'deny', or 'ask_user'."""
        tool_name = tool_call.name
        tool_input = tool_call.input
        args_str = _serialize_args(tool_input)

        # Layer 0: Plan mode exception — auto-allow all
        if self._plan_mode is not None and getattr(self._plan_mode, "in_plan", False):
            return "allow"

        # Layer 1b: Dangerous command blacklist (run_command only)
        if tool_name == "run_command" and "command" in tool_input:
            blocked, _ = self._dangerous_detector.detect(str(tool_input["command"]))
            if blocked:
                return "deny"

        # Layer 2: Path sandbox (file tools only)
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

        # Layer 1: Read-only tools auto-allow (after sandbox for file security)
        if self._registry is not None:
            try:
                tool = self._registry.get(tool_name)
                if tool.is_read_only:
                    return "allow"
            except KeyError:
                pass

        # Layer 3: Rule engine (session first, then base)
        result = self._session_rules.match(tool_name, args_str)
        if result is not None:
            return result
        result = self._base_rules.match(tool_name, args_str)
        if result is not None:
            return result

        # Layer 3.5: Session-level "don't ask again" set
        if (tool_name, args_str) in self._session_allow_set:
            return "allow"

        # Layer 4: Mode matrix fallback
        return mode_fallback(self._mode, tool_name)

        # Layer 5: HITL — handled by agent.py when L4 returns "ask_user"
