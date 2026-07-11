from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from opcode_cli.agent.events import ToolResultEvent
from opcode_cli.provider.base import ToolCall
from opcode_cli.tools.base import ToolResult
from opcode_cli.tools.registry import ToolRegistry


class ToolBatcher:
    def __init__(self, registry: ToolRegistry, working_dir: str | None = None) -> None:
        self._registry = registry
        self._working_dir = working_dir

    async def execute(
        self,
        tool_calls: list[ToolCall],
        pre_hook: Callable[[ToolCall], Awaitable[ToolResult | None]] | None = None,
    ) -> AsyncIterator[ToolResultEvent]:
        read_only_calls: list[ToolCall] = []
        side_effect_calls: list[ToolCall] = []
        results: dict[str, ToolResult] = {}

        for tc in tool_calls:
            try:
                tool = self._registry.get(tc.name)
                if tool.is_read_only:
                    read_only_calls.append(tc)
                else:
                    side_effect_calls.append(tc)
            except KeyError:
                results[tc.id] = ToolResult(
                    success=False,
                    content="",
                    error=f"unknown tool: '{tc.name}'",
                )

        if read_only_calls:

            async def _run_read_only(tc: ToolCall) -> tuple[str, ToolResult]:
                if pre_hook:
                    intercept = await pre_hook(tc)
                    if intercept is not None:
                        return tc.id, intercept
                try:
                    r = await self._registry.execute(tc.name, working_dir=self._working_dir, **tc.input)
                    return tc.id, r
                except Exception as e:
                    return tc.id, ToolResult(success=False, content="", error=str(e))

            gathered = await asyncio.gather(
                *[_run_read_only(tc) for tc in read_only_calls]
            )
            for tool_id, result in gathered:
                results[tool_id] = result

        for tc in side_effect_calls:
            if tc.id in results:
                continue
            if pre_hook:
                intercept = await pre_hook(tc)
                if intercept is not None:
                    results[tc.id] = intercept
                    continue
            try:
                result = await self._registry.execute(tc.name, working_dir=self._working_dir, **tc.input)
            except Exception as e:
                result = ToolResult(success=False, content="", error=str(e))
            results[tc.id] = result

        for tc in tool_calls:
            result = results[tc.id]
            yield ToolResultEvent(tool_id=tc.id, name=tc.name, result=result)
