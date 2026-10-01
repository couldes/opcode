"""Compatibility exports for the canonical file-tool implementation."""

from opcode_cli.tools.file_ops import (
    BaseFileSystemTool,
    EditFileParams,
    EditFileTool,
    FileOperationParams,
    ReadFileParams,
    ReadFileTool,
    WriteFileParams,
    WriteFileTool,
)

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
