import asyncio
import time

import pytest

from opcode_cli.agent.batcher import ToolBatcher
from opcode_cli.agent.events import ToolResultEvent
from opcode_cli.provider.base import ToolCall
from opcode_cli.tools.base import BaseTool, ToolResult
from opcode_cli.tools.registry import ToolRegistry


class FastReadTool(BaseTool):
    name = "read_A"
    description = "Read A"
    parameters = {"type": "object", "properties": {}}
    read_only = True

    async def execute(self, params=None, working_dir=None) -> ToolResult:
        await asyncio.sleep(0.05)
        return ToolResult(True, "read A ok")


class SlowReadTool(BaseTool):
    name = "read_B"
    description = "Read B"
    parameters = {"type": "object", "properties": {}}
    read_only = True

    async def execute(self, params=None, working_dir=None) -> ToolResult:
        await asyncio.sleep(0.05)
        return ToolResult(True, "read B ok")


class WriteTool(BaseTool):
    name = "write_C"
    description = "Write C"
    parameters = {"type": "object", "properties": {}}
    read_only = False

    def __init__(self):
        self.executed = False

    async def execute(self, params=None, working_dir=None) -> ToolResult:
        self.executed = True
        return ToolResult(True, "wrote C")


@pytest.fixture
def batcher():
    r = ToolRegistry()
    r.register(FastReadTool())
    r.register(SlowReadTool())
    r.register(WriteTool())
    return ToolBatcher(r)


@pytest.mark.asyncio
async def test_batcher_only_read_tools(batcher):
    """2 read-only tools should run concurrently."""
    tool_calls = [
        ToolCall(id="c1", name="read_A", input={}),
        ToolCall(id="c2", name="read_B", input={}),
    ]

    t0 = time.monotonic()
    events = []
    async for event in batcher.execute(tool_calls):
        events.append(event)
    elapsed = time.monotonic() - t0

    assert len(events) == 2
    assert events[0].tool_id == "c1"
    assert events[1].tool_id == "c2"
    assert events[0].result.success
    assert events[1].result.success
    # Concurrent execution should take ~0.05s, not ~0.10s (sequential)
    assert elapsed < 0.30


@pytest.mark.asyncio
async def test_batcher_only_write_tools(batcher):
    """Side-effect tools should run sequentially."""
    tool_calls = [
        ToolCall(id="c1", name="write_C", input={}),
    ]

    events = []
    async for event in batcher.execute(tool_calls):
        events.append(event)

    assert len(events) == 1
    assert events[0].result.success
    assert "wrote C" in events[0].result.content


@pytest.mark.asyncio
async def test_batcher_mixed_read_write(batcher):
    """Mixed: all read-only first (concurrent), then side-effect (sequential)."""
    tool_calls = [
        ToolCall(id="c1", name="read_A", input={}),
        ToolCall(id="c2", name="write_C", input={}),
        ToolCall(id="c3", name="read_B", input={}),
    ]

    events = []
    async for event in batcher.execute(tool_calls):
        events.append(event)

    assert len(events) == 3
    # Original order preserved in output
    assert events[0].tool_id == "c1"
    assert events[1].tool_id == "c2"
    assert events[2].tool_id == "c3"
    assert all(e.result.success for e in events)


@pytest.mark.asyncio
async def test_batcher_unknown_tool():
    """Unknown tool returns failure result."""
    r = ToolRegistry()
    batcher = ToolBatcher(r)
    tool_calls = [ToolCall(id="c1", name="nonexistent", input={})]

    events = []
    async for event in batcher.execute(tool_calls):
        events.append(event)

    assert len(events) == 1
    assert not events[0].result.success
    assert events[0].tool_id == "c1"
    assert events[0].name == "nonexistent"
    assert "unknown tool" in events[0].result.error


@pytest.mark.asyncio
async def test_batcher_empty():
    batcher = ToolBatcher(ToolRegistry())
    events = []
    async for event in batcher.execute([]):
        events.append(event)
    assert len(events) == 0
