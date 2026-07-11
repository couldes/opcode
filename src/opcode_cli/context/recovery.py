"""Recovery context — records file reads & skill calls for compression injection.

Integrates with ContextManager._do_compress() to attach recovery context
before summarization. The recording is triggered from Agent after tools execute.
"""

from opcode_cli.context.types import RecoveryState

# Re-export for convenience
__all__ = ["RecoveryState", "record_tool_invocation"]


def record_tool_invocation(
    recovery: RecoveryState,
    tool_name: str,
    tool_args: dict | None = None,
    result_content: str = "",
) -> None:
    """Record a tool invocation into RecoveryState.

    Auto-detects ReadFile and LoadSkill to populate the appropriate
    recovery context sections. Other tool calls are ignored.
    """
    if tool_name in ("read_file", "read"):
        path = ""
        if tool_args:
            path = tool_args.get("path", tool_args.get("file_path", ""))
        if path:
            recovery.record_file_read(str(path), result_content)

    elif tool_name in ("load_skill", "install_skill"):
        name = ""
        if tool_args:
            name = tool_args.get("name", "")
        if name:
            args_str = str(tool_args) if tool_args else ""
            recovery.record_skill_call(str(name), args_str)
