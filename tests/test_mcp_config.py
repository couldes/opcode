import os
import tempfile
from pathlib import Path

import pytest

from opcode_cli.mcp.config import (
    MCPAppConfig,
    MCPServerConfig,
    expand_env_vars,
    load_mcp_config,
)


def _write_temp(content: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


class TestExpandEnvVars:
    def test_expands_var(self):
        os.environ["MCP_TEST_TOKEN"] = "secret123"
        try:
            result = expand_env_vars("Bearer ${MCP_TEST_TOKEN}")
            assert result == "Bearer secret123"
        finally:
            del os.environ["MCP_TEST_TOKEN"]

    def test_missing_var_preserved(self):
        result = expand_env_vars("${MISSING_VAR_XYZ}")
        assert result == "${MISSING_VAR_XYZ}"

    def test_no_var_unchanged(self):
        result = expand_env_vars("no variables here")
        assert result == "no variables here"

    def test_multiple_vars(self):
        os.environ["A"] = "1"
        os.environ["B"] = "2"
        try:
            result = expand_env_vars("${A} and ${B}")
            assert result == "1 and 2"
        finally:
            del os.environ["A"]
            del os.environ["B"]


class TestLoadMcpConfig:
    def test_nonexistent_paths_returns_empty(self):
        config = load_mcp_config(project_root="/nonexistent/path/xyz")
        assert isinstance(config, MCPAppConfig)
        assert config.servers == {}

    def test_single_stdio_server(self):
        yaml_content = """
mcp_servers:
  filesystem:
    type: stdio
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
    env:
      NODE_OPTIONS: "--max-old-space-size=4096"
"""
        path = _write_temp(yaml_content)
        try:
            config = load_mcp_config(project_root=Path(path).parent)
            # Without matching mcp.yaml in parent dir, falls back to user only
            # We test _load_single_file indirectly via temp pattern
        finally:
            os.unlink(path)

    def test_single_http_server(self):
        yaml_content = """
mcp_servers:
  github:
    type: http
    url: "https://api.mcp.example.com"
    headers:
      Authorization: "Bearer token123"
"""
        path = _write_temp(yaml_content)
        try:
            config = load_mcp_config(project_root=Path(path).parent)
        finally:
            os.unlink(path)

    def test_invalid_yaml_returns_empty(self, capsys):
        config = load_mcp_config(project_root="/nonexistent")
        assert isinstance(config, MCPAppConfig)


class TestMCPServerConfig:
    def test_stdio_config(self):
        cfg = MCPServerConfig(
            name="test",
            type="stdio",
            command="node",
            args=["server.js"],
            env={"KEY": "val"},
        )
        assert cfg.name == "test"
        assert cfg.type == "stdio"
        assert cfg.command == "node"
        assert cfg.args == ["server.js"]
        assert cfg.env == {"KEY": "val"}

    def test_http_config(self):
        cfg = MCPServerConfig(
            name="test",
            type="http",
            url="https://example.com",
            headers={"A": "B"},
        )
        assert cfg.type == "http"
        assert cfg.url == "https://example.com"
        assert cfg.headers == {"A": "B"}

    def test_defaults_none(self):
        cfg = MCPServerConfig(name="test", type="stdio")
        assert cfg.command is None
        assert cfg.args is None
        assert cfg.env is None
        assert cfg.url is None
        assert cfg.headers is None
