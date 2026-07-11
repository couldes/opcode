from pathlib import Path

from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class GlobFindParams(BaseModel):
    pattern: str
    path: str = "."


class GlobFindTool(Tool):
    name = "glob_find"
    description = (
        "Find files matching a glob pattern. "
        "Returns a list of matching file paths, one per line. "
        "Prefer this tool over Bash find/ls. "
        "Multiple independent searches can be called in parallel in the same turn."
    )
    params_model = GlobFindParams
    category = ToolCategory.READ
    is_concurrency_safe = True
    MAX_RESULTS = 200

    async def execute(self, params: GlobFindParams, working_dir: str | None = None) -> ToolResult:
        path = params.path
        if working_dir and path == ".":
            path = working_dir
        base = Path(path)
        if working_dir and not base.is_absolute():
            base = Path(working_dir) / path
        if not base.exists():
            return ToolResult(False, "", f"path not found: {path}")

        matches = list(base.glob(params.pattern))
        if not matches:
            return ToolResult(True, f"no files found matching: {params.pattern}")

        lines = []
        for p in matches[:self.MAX_RESULTS]:
            lines.append(str(p))

        result = "\n".join(lines)
        if len(matches) > self.MAX_RESULTS:
            result += f"\n\n[... {len(matches) - self.MAX_RESULTS} more results truncated]"

        return ToolResult(True, result)
