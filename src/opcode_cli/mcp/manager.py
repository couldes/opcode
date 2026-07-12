from contextlib import AsyncExitStack
from dataclasses import dataclass

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

from opcode_cli.mcp.adapter import MCPToolAdapter
from opcode_cli.mcp.config import MCPAppConfig, MCPServerConfig
from opcode_cli.tools.registry import ToolRegistry


@dataclass
class MCPSession:
    server_name: str
    session: ClientSession
    tools: list
    _exit_stack: AsyncExitStack


class MCPServerManager:
    def __init__(self, config: MCPAppConfig):
        self._config = config
        self._sessions: dict[str, MCPSession] = {}
        self._registered = False
        self._global_exit_stack = AsyncExitStack()

    def get_session(self, name: str) -> MCPSession | None:
        return self._sessions.get(name)

    async def ensure_registered(self, registry: ToolRegistry) -> None:
        if self._registered:
            return

        for name, cfg in self._config.servers.items():
            if name in self._sessions:
                continue
            try:
                mcp_session = await self._connect_server(name, cfg)
                self._sessions[name] = mcp_session
                for tool_def in mcp_session.tools:
                    adapter = MCPToolAdapter(
                        server_name=name,
                        tool_name=tool_def.name,
                        description=tool_def.description or "",
                        parameters=tool_def.inputSchema,
                        session_provider=lambda s=mcp_session: _get_session(s),
                    )
                    registry.register(adapter)
            except Exception as e:
                print(f"Warning: failed to connect MCP server '{name}': {e}")

        self._registered = True

    async def _connect_server(self, name: str, cfg: MCPServerConfig) -> MCPSession:
        if cfg.type == "stdio":
            params = StdioServerParameters(
                command=cfg.command or "",
                args=cfg.args or [],
                env=cfg.env,
            )
            read, write = await self._global_exit_stack.enter_async_context(
                stdio_client(params)
            )
        elif cfg.type == "http":
            read, write = await self._global_exit_stack.enter_async_context(
                streamablehttp_client(
                    url=cfg.url or "",
                    headers=cfg.headers,
                )
            )
        else:
            raise ValueError(f"Unknown MCP server type: {cfg.type}")

        session = await self._global_exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()
        result = await session.list_tools()
        return MCPSession(
            server_name=name,
            session=session,
            tools=result.tools,
            _exit_stack=self._global_exit_stack,
        )

    async def disconnect_all(self) -> None:
        try:
            await self._global_exit_stack.aclose()
        except RuntimeError:
            pass
        self._sessions.clear()
        self._registered = False


async def _get_session(s: MCPSession) -> ClientSession:
    return s.session
