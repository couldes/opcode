import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


_VAR_PATTERN = re.compile(r'\$\{(\w+)\}')


@dataclass
class MCPServerConfig:
    name: str
    type: str
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None


@dataclass
class MCPAppConfig:
    servers: dict[str, MCPServerConfig] = field(default_factory=dict)


def expand_env_vars(value: str) -> str:
    def _replacer(m: re.Match) -> str:
        var_name = m.group(1)
        return os.environ.get(var_name, m.group(0))
    return _VAR_PATTERN.sub(_replacer, value)


def _expand_dict(d: dict[str, str]) -> dict[str, str]:
    return {k: expand_env_vars(v) for k, v in d.items()}


def _load_single_file(path: Path) -> MCPAppConfig | None:
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Warning: failed to parse MCP config '{path}': {e}")
        return None

    if not data:
        return None

    raw_servers = data.get("mcp_servers")
    if not raw_servers:
        return None

    servers: dict[str, MCPServerConfig] = {}
    for name, raw in raw_servers.items():
        server_type = raw.get("type", "")
        if server_type not in ("stdio", "http"):
            print(f"Warning: unknown MCP server type '{server_type}' for '{name}', skipping")
            continue

        servers[name] = MCPServerConfig(
            name=name,
            type=server_type,
            command=raw.get("command"),
            args=raw.get("args"),
            env=_expand_dict(raw["env"]) if raw.get("env") else None,
            url=raw.get("url"),
            headers=_expand_dict(raw["headers"]) if raw.get("headers") else None,
        )

    return MCPAppConfig(servers=servers)


def load_mcp_config(project_root: str | None = None) -> MCPAppConfig:
    user_path = Path.home() / ".opcode" / "mcp.yaml"
    merged: dict[str, MCPServerConfig] = {}

    user_config = _load_single_file(user_path)
    if user_config:
        merged.update(user_config.servers)

    if project_root:
        project_path = Path(project_root) / ".opcode" / "mcp.yaml"
        project_config = _load_single_file(project_path)
        if project_config:
            merged.update(project_config.servers)

    return MCPAppConfig(servers=merged)
