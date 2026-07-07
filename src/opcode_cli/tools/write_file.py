from pathlib import Path

from opcode_cli.tools.base import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    name = "write_file"
    description = (
        "Write content to a file. Creates parent directories if needed. "
        "Overwrites existing files. "
        "Prefer this tool over Bash echo >. "
        "The path parameter must use an absolute path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write.",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file.",
            },
        },
        "required": ["path", "content"],
    }
    read_only = False

    async def execute(self, path: str, content: str) -> ToolResult:
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except PermissionError:
            return ToolResult(False, "", f"permission denied: {path}")
        return ToolResult(True, f"wrote {len(content)} bytes to {path}")
