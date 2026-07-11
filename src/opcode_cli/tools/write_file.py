from pathlib import Path

from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class WriteFileParams(BaseModel):
    path: str
    content: str


class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "Write content to a file. Creates parent directories if needed. "
        "Overwrites existing files. "
        "Prefer this tool over Bash echo >. "
        "The path parameter must use an absolute path."
    )
    params_model = WriteFileParams
    category = ToolCategory.WRITE

    async def execute(self, params: WriteFileParams, working_dir: str | None = None) -> ToolResult:
        p = Path(params.path)
        if working_dir and not p.is_absolute():
            p = Path(working_dir) / params.path
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(params.content, encoding="utf-8")
        except PermissionError:
            return ToolResult(False, "", f"permission denied: {params.path}")
        return ToolResult(True, f"wrote {len(params.content)} bytes to {params.path}")
