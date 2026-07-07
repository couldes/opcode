from pathlib import Path

from opcode_cli.tools.base import BaseTool, ToolResult


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "Replace a string in a file by exact unique match. "
        "The old_string must match exactly once in the file. "
        "If 0 or multiple matches, the edit is rejected with a clear error — "
        "provide more surrounding context to make the match unique. "
        "Prefer this tool over Bash sed. "
        "Must read the file with ReadFile first to obtain the exact old_string. "
        "The path parameter must use an absolute path."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit.",
            },
            "old_string": {
                "type": "string",
                "description": "The exact string in the file to replace.",
            },
            "new_string": {
                "type": "string",
                "description": "The string to replace it with.",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }
    read_only = False

    async def execute(
        self, path: str, old_string: str, new_string: str
    ) -> ToolResult:
        p = Path(path)
        if not p.exists():
            return ToolResult(False, "", f"file not found: {path}")

        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, "", f"cannot edit binary file: {path}")

        count = content.count(old_string)
        if count == 0:
            return ToolResult(False, "", f"old_string not found in {path}")
        if count > 1:
            return ToolResult(
                False,
                "",
                f"found {count} matches in {path}, "
                "please include more surrounding context to make it unique",
            )

        new_content = content.replace(old_string, new_string)
        p.write_text(new_content, encoding="utf-8")
        return ToolResult(True, f"file edited: {path}")
