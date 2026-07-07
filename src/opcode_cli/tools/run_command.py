import asyncio

from opcode_cli.tools.base import BaseTool, ToolResult


class RunCommandTool(BaseTool):
    name = "run_command"
    description = (
        "Execute a shell command. Returns stdout, stderr, and exit code. "
        "The description parameter must clearly state what the command does. "
        "Prefer dedicated tools (ReadFile, WriteFile, EditFile, GlobFind, GrepSearch) "
        "over this tool for file operations."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command (optional).",
            },
        },
        "required": ["command"],
    }
    read_only = False
    MAX_OUTPUT = 50 * 1024

    async def execute(self, command: str, cwd: str | None = None) -> ToolResult:
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except OSError as e:
            return ToolResult(False, "", f"failed to execute command: {e}")

        stdout_str = stdout.decode("utf-8", errors="replace")
        stderr_str = stderr.decode("utf-8", errors="replace")

        if len(stdout_str) > self.MAX_OUTPUT:
            stdout_str = stdout_str[:self.MAX_OUTPUT] + "\n[... stdout truncated]"
        if len(stderr_str) > self.MAX_OUTPUT:
            stderr_str = stderr_str[:self.MAX_OUTPUT] + "\n[... stderr truncated]"

        output = (
            f"exit_code: {process.returncode}\n"
            f"stdout:\n{stdout_str}\n"
            f"stderr:\n{stderr_str}"
        )
        return ToolResult(success=(process.returncode == 0), content=output)
