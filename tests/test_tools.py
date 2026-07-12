import asyncio
import os
from pathlib import Path

import pytest

from opcode_cli.tools.base import ToolResult
from opcode_cli.tools.edit_file import EditFileParams, EditFileTool
from opcode_cli.tools.glob_find import GlobFindParams, GlobFindTool
from opcode_cli.tools.grep_search import GrepSearchParams, GrepSearchTool
from opcode_cli.tools.read_file import ReadFileParams, ReadFileTool
from opcode_cli.tools.registry import ToolRegistry
from opcode_cli.tools.run_command import RunCommandParams, RunCommandTool
from opcode_cli.tools.write_file import WriteFileParams, WriteFileTool


# --- read_file ---

async def test_read_file_success(tmp_path):
    f = tmp_path / "test.txt"
    f.write_text("hello world", encoding="utf-8")
    result = await ReadFileTool().execute(ReadFileParams(path=str(f)))
    assert result.success
    assert result.content == "hello world"


async def test_read_file_not_found():
    result = await ReadFileTool().execute(ReadFileParams(path="/nonexistent/path/xyz.txt"))
    assert not result.success
    assert "not found" in result.error


async def test_read_file_empty(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("", encoding="utf-8")
    result = await ReadFileTool().execute(ReadFileParams(path=str(f)))
    assert result.success
    assert result.content == ""


# --- write_file ---

async def test_write_file_creates_file(tmp_path):
    f = tmp_path / "new.txt"
    result = await WriteFileTool().execute(WriteFileParams(path=str(f), content="hello"))
    assert result.success
    assert f.read_text(encoding="utf-8") == "hello"


async def test_write_file_creates_parent_dir(tmp_path):
    f = tmp_path / "subdir" / "file.txt"
    result = await WriteFileTool().execute(WriteFileParams(path=str(f), content="data"))
    assert result.success
    assert f.read_text(encoding="utf-8") == "data"


# --- edit_file ---

async def test_edit_file_single_match(tmp_path):
    f = tmp_path / "edit.txt"
    f.write_text("hello world", encoding="utf-8")
    result = await EditFileTool().execute(
        EditFileParams(path=str(f), old_string="hello", new_string="hi")
    )
    assert result.success
    assert f.read_text(encoding="utf-8") == "hi world"


async def test_edit_file_zero_matches(tmp_path):
    f = tmp_path / "edit.txt"
    f.write_text("hello world", encoding="utf-8")
    result = await EditFileTool().execute(
        EditFileParams(path=str(f), old_string="xyz", new_string="abc")
    )
    assert not result.success
    assert "not found" in result.error


async def test_edit_file_multiple_matches(tmp_path):
    f = tmp_path / "edit.txt"
    f.write_text("hello world\nhello again", encoding="utf-8")
    result = await EditFileTool().execute(
        EditFileParams(path=str(f), old_string="hello", new_string="hi")
    )
    assert not result.success
    assert "2 matches" in result.error


async def test_edit_file_not_found():
    result = await EditFileTool().execute(
        EditFileParams(path="/nonexistent/x.txt", old_string="a", new_string="b")
    )
    assert not result.success
    assert "not found" in result.error


# --- run_command ---

async def test_run_command_echo():
    result = await RunCommandTool().execute(RunCommandParams(command="echo hello"))
    assert result.success
    assert "hello" in result.content
    assert "exit_code: 0" in result.content


async def test_run_command_nonzero_exit():
    result = await RunCommandTool().execute(RunCommandParams(command="exit 1"))
    assert not result.success
    assert "exit_code: 1" in result.content


async def test_run_command_not_found():
    result = await RunCommandTool().execute(RunCommandParams(command="nonexistent_cmd_xyz_123"))
    assert not result.success


# --- glob_find ---

async def test_glob_find_matches(tmp_path):
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "c.txt").write_text("")
    result = await GlobFindTool().execute(GlobFindParams(pattern="*.py", path=str(tmp_path)))
    assert result.success
    assert "a.py" in result.content
    assert "b.py" in result.content
    assert "c.txt" not in result.content


async def test_glob_find_no_matches(tmp_path):
    result = await GlobFindTool().execute(GlobFindParams(pattern="*.xyz", path=str(tmp_path)))
    assert result.success
    assert "no files found" in result.content


async def test_glob_find_invalid_path():
    result = await GlobFindTool().execute(
        GlobFindParams(pattern="*.py", path="/nonexistent/path")
    )
    assert not result.success


# --- grep_search ---

async def test_grep_search_matches(tmp_path):
    (tmp_path / "a.py").write_text("import os\nprint(1)\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("import sys\n", encoding="utf-8")
    result = await GrepSearchTool().execute(GrepSearchParams(pattern="import", path=str(tmp_path)))
    assert result.success
    assert "import os" in result.content
    assert "import sys" in result.content


async def test_grep_search_no_matches(tmp_path):
    (tmp_path / "a.py").write_text("hello", encoding="utf-8")
    result = await GrepSearchTool().execute(GrepSearchParams(pattern="xyz123", path=str(tmp_path)))
    assert result.success
    assert "no matches found" in result.content


async def test_grep_search_invalid_regex():
    result = await GrepSearchTool().execute(GrepSearchParams(pattern="["))
    assert not result.success
    assert "invalid regex" in result.error


# --- registry ---

async def test_registry_register_and_get():
    r = ToolRegistry()
    tool = ReadFileTool()
    r.register(tool)
    assert r.get("read_file") is tool
    assert len(r.list_tools()) == 1


def test_registry_duplicate_register():
    r = ToolRegistry()
    r.register(ReadFileTool())
    with pytest.raises(ValueError):
        r.register(ReadFileTool())


def test_registry_get_missing():
    r = ToolRegistry()
    with pytest.raises(KeyError):
        r.get("nonexistent")


def test_registry_to_anthropic_format():
    r = ToolRegistry()
    r.register(ReadFileTool())
    fmt = r.to_anthropic_format()
    assert len(fmt) == 1
    assert fmt[0]["name"] == "read_file"
    assert "description" in fmt[0]
    assert "input_schema" in fmt[0]


def test_registry_to_openai_format():
    r = ToolRegistry()
    r.register(WriteFileTool())
    fmt = r.to_openai_format()
    assert len(fmt) == 1
    assert fmt[0]["type"] == "function"
    assert fmt[0]["function"]["name"] == "write_file"


async def test_registry_execute_timeout():
    r = ToolRegistry(timeout=0.1)

    class SlowTool(ReadFileTool):
        name = "slow"
        params_model = None  # 绕过 ReadFileParams 验证

        async def execute(self, params=None, working_dir=None):
            await asyncio.sleep(10)
            return ToolResult(True, "done")

    r.register(SlowTool())
    result = await r.execute("slow")
    assert not result.success
    assert "timed out" in result.error


async def test_registry_execute_exception():
    r = ToolRegistry()

    class CrashTool(ReadFileTool):
        name = "crash"
        params_model = None  # 绕过 ReadFileParams 验证

        async def execute(self, params=None, working_dir=None):
            raise ValueError("boom")

    r.register(CrashTool())
    result = await r.execute("crash")
    assert not result.success
    assert "boom" in result.error


# --- is_read_only declarations ---

def test_tools_is_read_only_attributes():
    assert ReadFileTool().is_read_only is True
    assert GlobFindTool().is_read_only is True
    assert GrepSearchTool().is_read_only is True
    assert WriteFileTool().is_read_only is False
    assert EditFileTool().is_read_only is False
    assert RunCommandTool().is_read_only is False


def test_registry_get_tools_by_read_only():
    r = ToolRegistry()
    r.register(ReadFileTool())
    r.register(WriteFileTool())
    r.register(GlobFindTool())
    r.register(EditFileTool())
    r.register(GrepSearchTool())
    r.register(RunCommandTool())

    ro = r.get_tools_by_read_only(read_only=True)
    rw = r.get_tools_by_read_only(read_only=False)

    assert len(ro) == 3
    assert len(rw) == 3
    ro_names = {t.name for t in ro}
    assert ro_names == {"read_file", "glob_find", "grep_search"}
    rw_names = {t.name for t in rw}
    assert rw_names == {"write_file", "edit_file", "run_command"}
