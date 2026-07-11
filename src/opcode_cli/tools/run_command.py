import asyncio

from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class RunCommandParams(BaseModel):
    command: str
    cwd: str | None = None


class RunCommandTool(Tool):
    name = "run_command"
    description = (
        "Execute a shell command. Returns stdout, stderr, and exit code. "
        "The description parameter must clearly state what the command does. "
        "Prefer dedicated tools (ReadFile, WriteFile, EditFile, GlobFind, GrepSearch) "
        "over this tool for file operations."
    )
    params_model = RunCommandParams
    category = ToolCategory.COMMAND
    MAX_OUTPUT = 50 * 1024

    async def execute(self, params: RunCommandParams, working_dir: str | None = None) -> ToolResult:
        effective_cwd = params.cwd or working_dir
        try:
            process = await asyncio.create_subprocess_shell(
                params.command,
                cwd=effective_cwd,
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
