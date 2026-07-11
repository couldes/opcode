from pathlib import Path

from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class EditFileParams(BaseModel):
    path: str
    old_string: str
    new_string: str


class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "Replace a string in a file by exact unique match. "
        "The old_string must match exactly once in the file. "
        "If 0 or multiple matches, the edit is rejected with a clear error. "
        "Provide more surrounding context to make the match unique. "
        "Must read the file with ReadFile first to obtain the exact old_string. "
        "The path parameter must use an absolute path."
    )
    params_model = EditFileParams
    category = ToolCategory.WRITE

    async def execute(self, params: EditFileParams, working_dir: str | None = None) -> ToolResult:
        p = Path(params.path)
        if working_dir and not p.is_absolute():
            p = Path(working_dir) / params.path
        if not p.exists():
            return ToolResult(False, "", f"file not found: {params.path}")

        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(False, "", f"cannot edit binary file: {params.path}")

        count = content.count(params.old_string)
        if count == 0:
            return ToolResult(False, "", f"old_string not found in {params.path}")
        if count > 1:
            return ToolResult(
                False, "",
                f"found {count} matches in {params.path}, "
                "please include more surrounding context to make it unique",
            )

        new_content = content.replace(params.old_string, params.new_string)
        p.write_text(new_content, encoding="utf-8")
        return ToolResult(True, f"file edited: {params.path}")
