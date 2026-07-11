from collections.abc import Awaitable, Callable

from mcp import ClientSession
from opcode_cli.tools.base import BaseTool, ToolCategory, ToolResult


class MCPToolAdapter(BaseTool):
    """Wraps an MCP Server tool as an opcode BaseTool."""

    def __init__(
        self,
        server_name: str,
        tool_name: str,
        description: str,
        parameters: dict,
        session_provider: Callable[[], Awaitable[ClientSession]],
    ):
        self.name = f"{server_name}__{tool_name}"
        self.description = description
        self.parameters = parameters
        self.category = ToolCategory.COMMAND
        self._server_name = server_name
        self._tool_name = tool_name
        self._session_provider = session_provider

    async def execute(self, **kwargs) -> ToolResult:
        session = await self._session_provider()
        try:
            result = await session.call_tool(self._tool_name, kwargs)
            parts: list[str] = []
            for item in result.content:
                if item.type == "text":
                    parts.append(item.text)
                elif item.type == "resource":
                    resource = item.resource
                    prefix = f"[resource: {resource.uri}]"
                    if hasattr(resource, "text"):
                        parts.append(f"{prefix}\n{resource.text}")
                    elif hasattr(resource, "blob"):
                        parts.append(f"{prefix}\n[blob: {len(resource.blob)} bytes]")
                elif item.type == "image":
                    parts.append(f"[image: {item.mimeType}] ({len(item.data)} bytes)")
                elif item.type == "audio":
                    parts.append(f"[audio: {item.mimeType}] ({len(item.data)} bytes)")
                elif item.type == "resource_link":
                    parts.append(f"[resource_link: {item.name}] ({item.uri})")
            return ToolResult(
                success=not result.isError,
                content="\n".join(parts),
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"MCP tool '{self._server_name}__{self._tool_name}' error: {e}",
            )
