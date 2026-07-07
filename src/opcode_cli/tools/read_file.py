from pathlib import Path

from opcode_cli.tools.base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = (
        "Read the entire contents of a file. Returns the file text. "
        "Prefer this tool over Bash cat/head/tail. "
        "The path parameter must use an absolute path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read.",
            },
        },
        "required": ["path"],
    }
    read_only = True
    MAX_SIZE = 100 * 1024

    async def execute(self, path: str) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(False, "", f"file not found: {path}")
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, "", f"cannot read binary file: {path}")
        if len(content) > self.MAX_SIZE:
            content = content[:self.MAX_SIZE] + (
                f"\n\n[... truncated, file is {len(content)} bytes total]"
            )
        return ToolResult(True, content)
