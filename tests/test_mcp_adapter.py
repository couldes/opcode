from unittest.mock import AsyncMock, MagicMock

import pytest

from opcode_cli.mcp.adapter import MCPToolAdapter
from opcode_cli.tools.base import BaseTool, ToolResult


@pytest.fixture
def mock_result():
    result = MagicMock()
    result.content = []
    result.isError = False
    return result


@pytest.fixture
def mock_session(mock_result):
    session = MagicMock()
    session.call_tool = AsyncMock(return_value=mock_result)
    return session


@pytest.fixture
def session_provider(mock_session):
    async def _provider():
        return mock_session

    return _provider


class TestMCPToolAdapter:
    def test_name_format(self, session_provider):
        adapter = MCPToolAdapter(
            server_name="my_server",
            tool_name="read_file",
            description="Read a file",
            parameters={"type": "object", "properties": {}},
            session_provider=session_provider,
        )
        assert adapter.name == "my_server__read_file"

    def test_is_base_tool(self, session_provider):
        adapter = MCPToolAdapter(
            server_name="s",
            tool_name="t",
            description="d",
            parameters={},
            session_provider=session_provider,
        )
        assert isinstance(adapter, BaseTool)

    def test_read_only_defaults_false(self, session_provider):
        adapter = MCPToolAdapter(
            server_name="s",
            tool_name="t",
            description="d",
            parameters={},
            session_provider=session_provider,
        )
        assert adapter.is_read_only is False

    @pytest.mark.asyncio
    async def test_execute_respects_timeout(self, session_provider):
        adapter = MCPToolAdapter(
            server_name="test_server",
            tool_name="test_tool",
            description="Test tool",
            parameters={"type": "object", "properties": {}},
            session_provider=session_provider,
        )
        result = await adapter.execute(arg1="val1")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_error_returns_tool_result(self, mock_session, session_provider):
        mock_session.call_tool.side_effect = RuntimeError("connection lost")

        adapter = MCPToolAdapter(
            server_name="test_server",
            tool_name="test_tool",
            description="Test tool",
            parameters={},
            session_provider=session_provider,
        )
        result = await adapter.execute()
        assert result.success is False
        assert "connection lost" in result.error
        assert "test_server__test_tool" in result.error
