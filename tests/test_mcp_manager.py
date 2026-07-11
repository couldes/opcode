from unittest.mock import MagicMock

import pytest

from opcode_cli.mcp.config import MCPAppConfig, MCPServerConfig
from opcode_cli.mcp.manager import MCPServerManager, MCPSession
from opcode_cli.tools.registry import ToolRegistry


@pytest.fixture
def empty_config():
    return MCPAppConfig(servers={})


@pytest.fixture
def registry():
    return ToolRegistry()


class TestMCPServerManager:
    def test_empty_config_no_error(self, empty_config, registry):
        manager = MCPServerManager(empty_config)
        assert manager is not None

    def test_get_session_returns_none_when_not_connected(self, empty_config):
        manager = MCPServerManager(empty_config)
        assert manager.get_session("nonexistent") is None

    @pytest.mark.asyncio
    async def test_ensure_registered_empty_config(self, empty_config, registry):
        manager = MCPServerManager(empty_config)
        await manager.ensure_registered(registry)
        # Should not raise, no servers to connect

    @pytest.mark.asyncio
    async def test_ensure_registered_idempotent(self, empty_config, registry):
        manager = MCPServerManager(empty_config)
        await manager.ensure_registered(registry)
        await manager.ensure_registered(registry)
        # Should not raise on second call

    @pytest.mark.asyncio
    async def test_disconnect_all_empty(self, empty_config):
        manager = MCPServerManager(empty_config)
        await manager.disconnect_all()
        # Should not raise when no sessions exist
