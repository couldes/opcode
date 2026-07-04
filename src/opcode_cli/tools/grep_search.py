import re
from pathlib import Path
from typing import BinaryIO

from opcode_cli.tools.base import BaseTool, ToolResult

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}


def _is_text_file(f: BinaryIO) -> bool:
    chunk = f.read(1024)
    f.seek(0)
    return b"\0" not in chunk


class GrepSearchTool(BaseTool):
    name = "grep_search"
    description = (
        "Search file contents using a regex pattern. "
        "Returns matching lines with file path and line number."
    )
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for.",
            },
            "path": {
                "type": "string",
                "description": "Directory to search in (default: current directory).",
            },
        },
        "required": ["pattern"],
    }
    MAX_MATCHES = 500

    async def execute(self, pattern: str, path: str = ".") -> ToolResult:
        base = Path(path)
        if not base.exists():
            return ToolResult(False, "", f"path not found: {path}")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult(False, "", f"invalid regex: {e}")

        matches: list[str] = []

        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in SKIP_DIRS for part in file_path.parts):
                continue

            try:
                with open(file_path, "rb") as f:
                    if not _is_text_file(f):
                        continue

                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if regex.search(line):
                            matches.append(
                                f"{file_path}:{lineno}: {line.rstrip()}"
                            )
                            if len(matches) >= self.MAX_MATCHES:
                                break
            except (OSError, PermissionError):
                continue

            if len(matches) >= self.MAX_MATCHES:
                break

        if not matches:
            return ToolResult(True, f"no matches found for: {pattern}")

        result = "\n".join(matches)
        if len(matches) >= self.MAX_MATCHES:
            result += f"\n\n[... {self.MAX_MATCHES} match limit reached, results truncated]"

        return ToolResult(True, result)
