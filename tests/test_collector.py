import pytest

from opcode_cli.agent.collector import StreamCollector
from opcode_cli.agent.events import TextDelta, ThinkingDelta, ToolCallStart, ToolCallInput
from opcode_cli.provider.base import StreamChunk


def async_iter(items):
    async def _iter():
        for item in items:
            yield item
    return _iter()


@pytest.mark.asyncio
async def test_collector_text_only():
    collector = StreamCollector()
    events = []
    async for event in collector.collect(async_iter([
        StreamChunk(content="Hello"),
        StreamChunk(content=" world"),
        StreamChunk(finish_reason="stop"),
    ])):
        events.append(event)

    assert len(events) == 2
    assert isinstance(events[0], TextDelta)
    assert events[0].content == "Hello"
    assert isinstance(events[1], TextDelta)
    assert events[1].content == " world"
    assert collector.content == "Hello world"
    assert collector.thinking == ""
    assert collector.tool_calls == []


@pytest.mark.asyncio
async def test_collector_thinking():
    collector = StreamCollector()
    events = []
    async for event in collector.collect(async_iter([
        StreamChunk(thinking="Let me think..."),
        StreamChunk(content="Answer"),
        StreamChunk(finish_reason="stop"),
    ])):
        events.append(event)

    assert len(events) == 2
    assert isinstance(events[0], ThinkingDelta)
    assert events[0].content == "Let me think..."
    assert isinstance(events[1], TextDelta)
    assert collector.thinking == "Let me think..."
    assert collector.content == "Answer"


@pytest.mark.asyncio
async def test_collector_tool_use():
    collector = StreamCollector()
    events = []
    async for event in collector.collect(async_iter([
        StreamChunk(
            tool_use={
                "id": "call_1",
                "name": "read_file",
                "input": {"path": "/tmp/test.txt"},
            }
        ),
        StreamChunk(finish_reason="tool_calls"),
    ])):
        events.append(event)

    assert len(events) == 2
    assert isinstance(events[0], ToolCallStart)
    assert events[0].tool_id == "call_1"
    assert events[0].name == "read_file"
    assert isinstance(events[1], ToolCallInput)
    assert events[1].tool_id == "call_1"

    assert len(collector.tool_calls) == 1
    tc = collector.tool_calls[0]
    assert tc.id == "call_1"
    assert tc.name == "read_file"
    assert tc.input == {"path": "/tmp/test.txt"}


@pytest.mark.asyncio
async def test_collector_text_plus_tool_use():
    collector = StreamCollector()
    events = []
    async for event in collector.collect(async_iter([
        StreamChunk(content="Let me check that file"),
        StreamChunk(
            tool_use={
                "id": "call_2",
                "name": "glob_find",
                "input": {"pattern": "*.py"},
            }
        ),
        StreamChunk(finish_reason="tool_calls"),
    ])):
        events.append(event)

    assert len(events) == 3
    assert isinstance(events[0], TextDelta)
    assert isinstance(events[1], ToolCallStart)
    assert isinstance(events[2], ToolCallInput)
    assert collector.content == "Let me check that file"
    assert len(collector.tool_calls) == 1


@pytest.mark.asyncio
async def test_collector_multiple_tool_uses():
    collector = StreamCollector()
    events = []
    async for event in collector.collect(async_iter([
        StreamChunk(
            tool_use={"id": "c1", "name": "read_file", "input": {"path": "a.txt"}}
        ),
        StreamChunk(
            tool_use={"id": "c2", "name": "read_file", "input": {"path": "b.txt"}}
        ),
        StreamChunk(finish_reason="tool_calls"),
    ])):
        events.append(event)

    assert len(collector.tool_calls) == 2
    assert collector.tool_calls[0].id == "c1"
    assert collector.tool_calls[1].id == "c2"
    assert collector.tool_calls[0].input == {"path": "a.txt"}
    assert collector.tool_calls[1].input == {"path": "b.txt"}
