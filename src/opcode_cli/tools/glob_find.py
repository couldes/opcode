from pathlib import Path

from opcode_cli.tools.base import BaseTool, ToolResult


class GlobFindTool(BaseTool):
    name = "glob_find"
    description = (
        "Find files matching a glob pattern. "
        "Returns a list of matching file paths, one per line. "
        "Prefer this tool over Bash find/ls. "
        "Multiple independent searches can be called in parallel in the same turn."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match (e.g. '**/*.py').",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory).",
            },
        },
        "required": ["pattern"],
    }
    read_only = True
    MAX_RESULTS = 200

    async def execute(self, pattern: str, path: str = ".", working_dir: str | None = None) -> ToolResult:
        if working_dir and path == ".":
            path = working_dir
        base = Path(path)
        if working_dir and not base.is_absolute():
            base = Path(working_dir) / path
        if not base.exists():
            return ToolResult(False, "", f"path not found: {path}")

        matches = list(base.glob(pattern))
        if not matches:
            return ToolResult(True, f"no files found matching: {pattern}")

        lines = []
        for p in matches[:self.MAX_RESULTS]:
            lines.append(str(p))

        result = "\n".join(lines)
        if len(matches) > self.MAX_RESULTS:
            result += f"\n\n[... {len(matches) - self.MAX_RESULTS} more results truncated]"

        return ToolResult(True, result)
