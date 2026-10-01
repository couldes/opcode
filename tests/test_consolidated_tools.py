from pathlib import Path

import pytest

from opcode_cli.tools.file_ops import (
    BaseFileSystemTool,
    EditFileParams,
    EditFileTool,
    ReadFileParams,
    ReadFileTool,
    WriteFileParams,
    WriteFileTool,
)
from opcode_cli.tools.search_tools import (
    BaseSearchTool,
    GlobFindParams,
    GlobFindTool,
    GrepSearchParams,
    GrepSearchTool,
)


def test_file_tools_share_filesystem_base():
    assert issubclass(ReadFileTool, BaseFileSystemTool)
    assert issubclass(WriteFileTool, BaseFileSystemTool)
    assert issubclass(EditFileTool, BaseFileSystemTool)


@pytest.mark.asyncio
async def test_consolidated_file_tools_preserve_existing_behavior(tmp_path):
    path = tmp_path / "nested" / "example.txt"

    write_result = await WriteFileTool().execute(
        WriteFileParams(path=str(path), content="before")
    )
    assert write_result.success

    edit_result = await EditFileTool().execute(
        EditFileParams(path=str(path), old_string="before", new_string="after")
    )
    assert edit_result.success

    read_result = await ReadFileTool().execute(ReadFileParams(path=str(path)))
    assert read_result.success
    assert read_result.content == "after"


@pytest.mark.asyncio
async def test_consolidated_edit_requires_unique_match(tmp_path):
    path = tmp_path / "example.txt"
    path.write_text("repeat\nrepeat", encoding="utf-8")

    result = await EditFileTool().execute(
        EditFileParams(path=str(path), old_string="repeat", new_string="changed")
    )

    assert not result.success
    assert "2 matches" in result.error


def test_search_tools_share_search_base():
    assert issubclass(GlobFindTool, BaseSearchTool)
    assert issubclass(GrepSearchTool, BaseSearchTool)


@pytest.mark.asyncio
async def test_consolidated_search_tools_preserve_existing_parameters(tmp_path):
    (tmp_path / "one.py").write_text("import os\n", encoding="utf-8")
    (tmp_path / "two.txt").write_text("import sys\n", encoding="utf-8")

    glob_result = await GlobFindTool().execute(
        GlobFindParams(pattern="*.py", path=str(tmp_path))
    )
    assert glob_result.success
    assert "one.py" in glob_result.content
    assert "two.txt" not in glob_result.content

    grep_result = await GrepSearchTool().execute(
        GrepSearchParams(pattern=r"import", path=str(tmp_path))
    )
    assert grep_result.success
    assert "one.py:1" in grep_result.content
    assert "two.txt:1" in grep_result.content


@pytest.mark.asyncio
async def test_search_tools_reject_invalid_regex(tmp_path):
    result = await GrepSearchTool().execute(
        GrepSearchParams(pattern="[", path=str(tmp_path))
    )

    assert not result.success
    assert "invalid regex" in result.error


def test_legacy_modules_export_consolidated_classes():
    from opcode_cli.tools.edit_file import EditFileTool as LegacyEditFileTool
    from opcode_cli.tools.glob_find import GlobFindTool as LegacyGlobFindTool
    from opcode_cli.tools.grep_search import GrepSearchTool as LegacyGrepSearchTool
    from opcode_cli.tools.read_file import ReadFileTool as LegacyReadFileTool
    from opcode_cli.tools.write_file import WriteFileTool as LegacyWriteFileTool

    assert LegacyReadFileTool is ReadFileTool
    assert LegacyWriteFileTool is WriteFileTool
    assert LegacyEditFileTool is EditFileTool
    assert LegacyGlobFindTool is GlobFindTool
    assert LegacyGrepSearchTool is GrepSearchTool


def test_infrastructure_tools_forward_to_canonical_implementation():
    from opcode_cli.infrastructure.tools.file_ops import (
        ReadFileTool as InfrastructureReadFileTool,
    )
    from opcode_cli.infrastructure.tools.search_tools import (
        GrepSearchTool as InfrastructureGrepSearchTool,
    )

    assert InfrastructureReadFileTool is ReadFileTool
    assert InfrastructureGrepSearchTool is GrepSearchTool
