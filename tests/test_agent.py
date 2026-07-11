import asyncio
from collections.abc import AsyncIterator

import pytest

from opcode_cli.agent.agent import Agent
from opcode_cli.agent.events import (
    DoneEvent,
    ErrorEvent,
    ProgressEvent,
    TextDelta,
    ToolCallStart,
    ToolResultEvent,
)
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk, ToolCall
from opcode_cli.tools.base import BaseTool, ToolResult
from opcode_cli.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "echo"
    description = "Echo tool"
    parameters = {
        "type": "object",
        "properties": {"msg": {"type": "string"}},
        "required": ["msg"],
    }
    read_only = True

    async def execute(self, msg: str = "", working_dir: str | None = None) -> ToolResult:
        return ToolResult(True, f"echo: {msg}")


class MockProvider(BaseProvider):
    def __init__(self, rounds: list[list[StreamChunk]] | None = None, should_fail: bool = False):
        self.rounds = rounds or []
        self.should_fail = should_fail
        self.last_messages: list[Message] = []
        self._round_idx = 0

    def chat(self, messages: list[Message]) -> Message:
        return Message(role="assistant", content="mock")

    async def achat(
        self, messages: list[Message], tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        self.last_messages = list(messages)
        if self.should_fail:
            raise RuntimeError("simulated API error")
        if self._round_idx < len(self.rounds):
            chunks = self.rounds[self._round_idx]
            self._round_idx += 1
        else:
            chunks = [StreamChunk(content="fallback"), StreamChunk(finish_reason="stop")]
        for c in chunks:
            yield c


@pytest.fixture
def registry():
    r = ToolRegistry()
    r.register(EchoTool())
    return r


@pytest.fixture
def agent(registry):
    prov = MockProvider()
    return Agent(prov, registry)


@pytest.mark.asyncio
async def test_agent_pure_text(registry):
    """Pure text response, no tool calls."""
    prov = MockProvider(rounds=[
        [StreamChunk(content="Hello"), StreamChunk(content=" world"), StreamChunk(finish_reason="stop")],
    ])
    agent = Agent(prov, registry)
    events = []
    async for e in agent.run("hi"):
        events.append(e)

    assert isinstance(events[0], ProgressEvent)
    assert isinstance(events[1], TextDelta)
    assert isinstance(events[-1], DoneEvent)
    assert events[-1].finish_reason == "stop"

    assert len(agent.messages) == 2
    assert agent.messages[0].role == "user"
    assert agent.messages[1].role == "assistant"
    assert agent.messages[1].content == "Hello world"


@pytest.mark.asyncio
async def test_agent_single_tool_call(registry):
    """Model calls tool, gets result, gives final answer."""
    prov = MockProvider(rounds=[
        [
            StreamChunk(content="Let me echo"),
            StreamChunk(tool_use={"id": "c1", "name": "echo", "input": {"msg": "test"}}),
            StreamChunk(finish_reason="tool_calls"),
        ],
        [StreamChunk(content="Echo done"), StreamChunk(finish_reason="stop")],
    ])
    agent = Agent(prov, registry)
    events = []
    async for e in agent.run("echo test"):
        events.append(e)

    event_types = [type(e) for e in events]
    assert ProgressEvent in event_types
    assert TextDelta in event_types
    assert ToolCallStart in event_types
    assert ToolResultEvent in event_types
    assert event_types[-1] is DoneEvent
    assert events[-1].finish_reason == "stop"

    assert len(agent.messages) == 4
    assert agent.messages[1].role == "assistant"
    assert agent.messages[1].tool_calls[0].name == "echo"
    assert agent.messages[2].role == "tool"
    assert "echo: test" in agent.messages[2].content
    assert agent.messages[3].role == "assistant"


@pytest.mark.asyncio
async def test_agent_max_iterations(registry):
    """Terminates when max_iterations reached."""
    rounds = []
    for i in range(5):
        rounds.append([
            StreamChunk(tool_use={"id": f"c{i}", "name": "echo", "input": {"msg": str(i)}}),
            StreamChunk(finish_reason="tool_calls"),
        ])

    prov = MockProvider(rounds=rounds)
    agent = Agent(prov, registry, max_iterations=2)
    events = []
    async for e in agent.run("loop"):
        events.append(e)

    assert events[-1].finish_reason == "max_iterations"


@pytest.mark.asyncio
async def test_agent_cancel(registry):
    """Cancel stops the loop."""
    rounds = []
    for i in range(5):
        rounds.append([
            StreamChunk(tool_use={"id": f"c{i}", "name": "echo", "input": {"msg": str(i)}}),
            StreamChunk(finish_reason="tool_calls"),
        ])

    prov = MockProvider(rounds=rounds)
    agent = Agent(prov, registry, max_iterations=10)
    agent.cancel()

    events = []
    async for e in agent.run("test"):
        events.append(e)

    assert events[-1].finish_reason == "cancelled"


@pytest.mark.asyncio
async def test_agent_stream_error(registry):
    """Provider exception yields ErrorEvent + DoneEvent("stream_error")."""
    prov = MockProvider(should_fail=True)
    agent = Agent(prov, registry)
    events = []
    async for e in agent.run("test"):
        events.append(e)

    assert any(isinstance(e, ErrorEvent) for e in events)
    assert events[-1].finish_reason == "stream_error"


@pytest.mark.asyncio
async def test_agent_unknown_tool_streak(registry):
    """Repeated unknown tools trigger termination."""
    rounds = []
    for i in range(5):
        rounds.append([
            StreamChunk(
                tool_use={"id": f"c{i}", "name": f"nonexistent_{i}", "input": {}}
            ),
            StreamChunk(finish_reason="tool_calls"),
        ])

    prov = MockProvider(rounds=rounds)
    agent = Agent(prov, registry, max_unknown_tools=3)
    events = []
    async for e in agent.run("test"):
        events.append(e)

    assert events[-1].finish_reason == "unknown_tool"


@pytest.mark.asyncio
async def test_agent_single_unknown_tool_tolerated(registry):
    """Single unknown tool is tolerated (streak < max)."""
    rounds = [
        [
            StreamChunk(tool_use={"id": "c1", "name": "nonexistent", "input": {}}),
            StreamChunk(finish_reason="tool_calls"),
        ],
        [StreamChunk(content="ok"), StreamChunk(finish_reason="stop")],
    ]

    prov = MockProvider(rounds=rounds)
    agent = Agent(prov, registry, max_unknown_tools=3)
    events = []
    async for e in agent.run("test"):
        events.append(e)

    assert events[-1].finish_reason == "stop"
