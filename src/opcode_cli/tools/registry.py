import asyncio
from typing import Any

from pydantic import BaseModel, ValidationError

from opcode_cli.tools.base import Tool, ToolResult


class ToolRegistry:

    def __init__(self, timeout: float = 30.0):
        self._tools: dict[str, Tool] = {}
        self._discovered: set[str] = set()
        self._timeout = timeout

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: '{tool.name}'")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"tool not found: '{name}'")
        return self._tools[name]

    def remove(self, name: str) -> None:
        self._tools.pop(name, None)

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def get_tools_by_read_only(self, read_only: bool) -> list[Tool]:
        return [t for t in self._tools.values() if t.is_read_only == read_only]

    def get_deferred_tool_names(self) -> list[str]:
        """返回已注册但尚未 discover 的 deferred 工具名称列表。"""
        return [
            name for name, tool in self._tools.items()
            if getattr(tool, "should_defer", False)
            and name not in self._discovered
        ]

    def search_deferred(self, query: str, max_results: int = 5) -> list[dict]:
        """在 deferred 工具中按名称+描述搜索。"""
        results: list[dict] = []
        q = query.lower()
        for name, tool in self._tools.items():
            if not getattr(tool, "should_defer", False):
                continue
            if name in self._discovered:
                continue
            score = 0
            if q in name.lower():
                score += 10
            if q in tool.description.lower():
                score += 5
            if score > 0:
                results.append({
                    "name": name,
                    "description": tool.description,
                    "score": score,
                })
        results.sort(key=lambda r: -r["score"])
        return results[:max_results]

    def mark_discovered(self, name: str) -> None:
        """标记一个 deferred 工具为已 discover，后续会加入 tool schema。"""
        self._discovered.add(name)

    def to_anthropic_format(self) -> list[dict]:
        return [
            tool.get_schema(fmt="anthropic")
            for tool in self._tools.values()
            if not getattr(tool, "should_defer", False) or tool.name in self._discovered
        ]

    def to_openai_format(self) -> list[dict]:
        return [
            tool.get_schema(fmt="openai")
            for tool in self._tools.values()
            if not getattr(tool, "should_defer", False) or tool.name in self._discovered
        ]

    async def execute(self, name: str, working_dir: str | None = None, **kwargs: Any) -> ToolResult:
        tool = self.get(name)
        try:
            if tool.params_model is not None:
                params = tool.params_model(**kwargs)
            else:
                params = kwargs  # type: ignore
            result = await asyncio.wait_for(
                tool.execute(params, working_dir=working_dir),
                timeout=self._timeout,
            )
            return result
        except ValidationError as e:
            return ToolResult(
                success=False,
                content="",
                error=f"tool '{name}' parameter validation error: {e}",
            )
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
