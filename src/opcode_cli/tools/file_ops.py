"""Shared implementation for file-system tools.

The individual public tools keep their original parameter models and behavior;
this module only owns the common path and text-file handling.
"""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class FileOperationParams(BaseModel):
    """Common parameters for file operations."""

    path: str


class ReadFileParams(FileOperationParams):
    """Parameters for reading a file."""


class WriteFileParams(FileOperationParams):
    """Parameters for writing a file."""

    content: str


class EditFileParams(FileOperationParams):
    """Parameters for an exact, unique string replacement."""

    old_string: str
    new_string: str


class BaseFileSystemTool(Tool):
    """Base class for file tools with shared path and text handling."""

    def resolve_path(self, path: str, working_dir: Optional[str] = None) -> Path:
        """Resolve a tool path using the same rules as the legacy tools."""
        resolved = Path(path)
        if working_dir and not resolved.is_absolute():
            resolved = Path(working_dir) / path
        return resolved

    def read_text(self, path: Path, display_path: str) -> tuple[str | None, ToolResult | None]:
        """Read UTF-8 text or return the standardized failure result."""
        try:
            return path.read_text(encoding="utf-8"), None
        except UnicodeDecodeError:
            return None, ToolResult(False, "", f"cannot read binary file: {display_path}")
        except OSError as exc:
            return None, ToolResult(False, "", f"cannot read file: {exc}")


class ReadFileTool(BaseFileSystemTool):
    """Read a UTF-8 text file, truncating very large results."""

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

    async def execute(
        self,
        params: ReadFileParams,
        working_dir: str | None = None,
    ) -> ToolResult:
        path = self.resolve_path(params.path, working_dir)
        if not path.exists():
            return ToolResult(False, "", f"file not found: {params.path}")

        content, error = self.read_text(path, params.path)
        if error is not None:
            return error
        assert content is not None

        if len(content) > self.MAX_SIZE:
            content = content[: self.MAX_SIZE] + (
                f"\n\n[... truncated, file is {len(content)} bytes total]"
            )
        return ToolResult(True, content)


class WriteFileTool(BaseFileSystemTool):
    """Write UTF-8 content, creating parent directories when necessary."""

    name = "write_file"
    description = (
        "Write content to a file. Creates parent directories if needed. "
        "Overwrites existing files. "
        "Prefer this tool over Bash echo >. "
        "The path parameter must use an absolute path."
    )
    params_model = WriteFileParams
    category = ToolCategory.WRITE

    async def execute(
        self,
        params: WriteFileParams,
        working_dir: str | None = None,
    ) -> ToolResult:
        path = self.resolve_path(params.path, working_dir)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(params.content, encoding="utf-8")
        except PermissionError:
            return ToolResult(False, "", f"permission denied: {params.path}")
        except OSError as exc:
            return ToolResult(False, "", f"cannot write file: {exc}")
        return ToolResult(True, f"wrote {len(params.content)} bytes to {params.path}")


class EditFileTool(BaseFileSystemTool):
    """Replace exactly one occurrence of a string in a UTF-8 text file."""

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

    async def execute(
        self,
        params: EditFileParams,
        working_dir: str | None = None,
    ) -> ToolResult:
        path = self.resolve_path(params.path, working_dir)
        if not path.exists():
            return ToolResult(False, "", f"file not found: {params.path}")

        content, error = self.read_text(path, params.path)
        if error is not None:
            return ToolResult(False, "", error.error)
        assert content is not None

        count = content.count(params.old_string)
        if count == 0:
            return ToolResult(False, "", f"old_string not found in {params.path}")
        if count > 1:
            return ToolResult(
                False,
                "",
                f"found {count} matches in {params.path}, "
                "please include more surrounding context to make it unique",
            )

        path.write_text(
            content.replace(params.old_string, params.new_string),
            encoding="utf-8",
        )
        return ToolResult(True, f"file edited: {params.path}")


__all__ = [
    "BaseFileSystemTool",
    "FileOperationParams",
    "ReadFileParams",
    "ReadFileTool",
    "WriteFileParams",
    "WriteFileTool",
    "EditFileParams",
    "EditFileTool",
]
