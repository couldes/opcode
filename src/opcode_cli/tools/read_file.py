from pathlib import Path

from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class ReadFileParams(BaseModel):
    path: str


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read the entire contents of a file. Returns the file text. "
        "Prefer this tool over Bash cat/head/tail. "
        "The path parameter must use an absolute path."
    )
    params_model = ReadFileParams
    category = ToolCategory.READ
    is_concurrency_safe = True
    MAX_SIZE = 100 * 1024

    async def execute(self, params: ReadFileParams, working_dir: str | None = None) -> ToolResult:
        p = Path(params.path)
        if working_dir and not p.is_absolute():
            p = Path(working_dir) / params.path
        if not p.exists():
            return ToolResult(False, "", f"file not found: {params.path}")
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, "", f"cannot read binary file: {params.path}")
        if len(content) > self.MAX_SIZE:
            content = content[:self.MAX_SIZE] + (
                f"\n\n[... truncated, file is {len(content)} bytes total]"
            )
        return ToolResult(True, content)
