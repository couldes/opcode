"""Shared implementation for file search tools."""

import re
import time
from pathlib import Path
from typing import Iterator, Optional

from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache"}


class SearchParams(BaseModel):
    """Common parameters for path-based searches."""

    pattern: str
    path: str = "."


class GlobFindParams(SearchParams):
    """Parameters for glob-based file discovery."""


class GrepSearchParams(SearchParams):
    """Parameters for regular-expression content search."""


class BaseSearchTool(Tool):
    """Base class for searches with shared path and traversal helpers."""

    category = ToolCategory.READ
    is_concurrency_safe = True

    def resolve_base(self, path: str, working_dir: Optional[str] = None) -> Path:
        """Resolve a search root using the legacy tool rules."""
        resolved_path = path
        if working_dir and path == ".":
            resolved_path = working_dir
        base = Path(resolved_path)
        if working_dir and not base.is_absolute():
            base = Path(working_dir) / resolved_path
        return base

    def validate_base(self, base: Path, display_path: str) -> ToolResult | None:
        """Return an error result when the search root is missing."""
        if not base.exists():
            return ToolResult(False, "", f"path not found: {display_path}")
        return None

    def iter_text_files(self, base: Path) -> Iterator[Path]:
        """Yield readable candidate files while skipping generated directories."""
        if base.is_file():
            yield base
            return

        for file_path in base.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in SKIP_DIRS for part in file_path.parts):
                continue
            yield file_path


class GlobFindTool(BaseSearchTool):
    """Find files matching a glob pattern."""

    name = "glob_find"
    description = (
        "Find files matching a glob pattern. "
        "Returns a list of matching file paths, one per line. "
        "Prefer this tool over Bash find/ls. "
        "Multiple independent searches can be called in parallel in the same turn."
    )
    params_model = GlobFindParams
    MAX_RESULTS = 200

    async def execute(
        self,
        params: GlobFindParams,
        working_dir: str | None = None,
    ) -> ToolResult:
        base = self.resolve_base(params.path, working_dir)
        error = self.validate_base(base, params.path)
        if error is not None:
            return error

        matches = list(base.glob(params.pattern))
        if not matches:
            return ToolResult(True, f"no files found matching: {params.pattern}")

        lines = [str(path) for path in matches[: self.MAX_RESULTS]]
        result = "\n".join(lines)
        if len(matches) > self.MAX_RESULTS:
            result += f"\n\n[... {len(matches) - self.MAX_RESULTS} more results truncated]"
        return ToolResult(True, result)


class GrepSearchTool(BaseSearchTool):
    """Search file contents using a regular-expression pattern."""

    name = "grep_search"
    description = (
        "Search file contents using a regex pattern. "
        "Returns matching lines with file path and line number. "
        "Prefer this tool over Bash grep/rg. "
        "Multiple independent searches can be called in parallel in the same turn."
    )
    params_model = GrepSearchParams
    MAX_MATCHES = 500

    async def execute(
        self,
        params: GrepSearchParams,
        working_dir: str | None = None,
    ) -> ToolResult:
        base = self.resolve_base(params.path, working_dir)
        error = self.validate_base(base, params.path)
        if error is not None:
            return error

        try:
            regex = re.compile(params.pattern)
        except re.error as exc:
            return ToolResult(False, "", f"invalid regex: {exc}")

        matches: list[str] = []
        for file_path in self.iter_text_files(base):
            try:
                with open(file_path, "rb") as file:
                    if b"\0" in file.read(1024):
                        continue

                with open(file_path, "r", encoding="utf-8", errors="replace") as file:
                    for line_number, line in enumerate(file, 1):
                        if regex.search(line):
                            matches.append(
                                f"{file_path}:{line_number}: {line.rstrip()}"
                            )
                            if len(matches) >= self.MAX_MATCHES:
                                break
            except (OSError, PermissionError):
                continue

            if len(matches) >= self.MAX_MATCHES:
                break

        if not matches:
            return ToolResult(True, f"no matches found for: {params.pattern}")

        result = "\n".join(matches)
        if len(matches) >= self.MAX_MATCHES:
            result += (
                f"\n\n[... {self.MAX_MATCHES} match limit reached, results truncated]"
            )
        return ToolResult(True, result)


__all__ = [
    "BaseSearchTool",
    "SearchParams",
    "GlobFindParams",
    "GlobFindTool",
    "GrepSearchParams",
    "GrepSearchTool",
]
