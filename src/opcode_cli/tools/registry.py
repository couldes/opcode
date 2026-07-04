import asyncio

from opcode_cli.tools.base import BaseTool, ToolResult


class ToolRegistry:

    def __init__(self, timeout: float = 30.0):
        self._tools: dict[str, BaseTool] = {}
        self._timeout = timeout

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: '{tool.name}'")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"tool not found: '{name}'")
        return self._tools[name]

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def to_anthropic_format(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in self._tools.values()
        ]

    def to_openai_format(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, **kwargs) -> ToolResult:
        tool = self.get(name)
        try:
            result = await asyncio.wait_for(
                tool.execute(**kwargs),
                timeout=self._timeout,
            )
            return result
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                content="",
                error=f"tool '{name}' timed out after {self._timeout}s",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"tool '{name}' error: {e}",
            )
