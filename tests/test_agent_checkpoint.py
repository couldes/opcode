from collections.abc import AsyncIterator
from pathlib import Path

from opcode_cli.agent.agent import Agent
from opcode_cli.agent.events import DoneEvent
from opcode_cli.checkpoint.manager import CheckpointManager
from opcode_cli.provider.base import BaseProvider, Message, StreamChunk
from opcode_cli.tools.registry import ToolRegistry
from opcode_cli.tools.write_file import WriteFileTool


class _MockProvider(BaseProvider):
    def __init__(self, rounds: list[list[StreamChunk]]):
        self.rounds = rounds
        self._idx = 0

    def chat(self, messages: list[Message]) -> Message:
        return Message(role="assistant", content="mock")

    async def achat(
        self, messages: list[Message], tools: list[dict] | None = None,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        if self._idx < len(self.rounds):
            chunks = self.rounds[self._idx]
            self._idx += 1
        else:
            chunks = [StreamChunk(content="done"), StreamChunk(finish_reason="stop")]
        for c in chunks:
            yield c


async def test_agent_checkpoint_lands_on_disk(tmp_path: Path):
    registry = ToolRegistry()
    registry.register(WriteFileTool())
    provider = _MockProvider([
        [
            StreamChunk(
                tool_use={"id": "c1", "name": "write_file", "input": {"path": "out.txt", "content": "hi"}}
            ),
            StreamChunk(finish_reason="tool_calls"),
        ],
        [StreamChunk(content="done"), StreamChunk(finish_reason="stop")],
    ])

    ckpt = CheckpointManager(
        store_dir=tmp_path / "ckpts",
        project_root=tmp_path,
        run_id="test-run",
    )
    agent = Agent(
        provider, registry,
        max_iterations=5,
        checkpoint_manager=ckpt,
        working_dir=str(tmp_path),
    )

    result = None
    async for ev in agent.run("do it"):
        if isinstance(ev, DoneEvent):
            result = ev
    assert result is not None
    assert result.finish_reason == "stop"

    # 快照落盘
    files = list((tmp_path / "ckpts").glob("test-run_*.json"))
    assert files, "checkpoint files should exist"

    # _task_input 记录
    snap = ckpt.latest_snapshot()
    assert snap is not None
    assert snap.task_input == "do it"
    # write_file 进入 changed_files 且磁盘状态被记录
    assert "out.txt" in snap.changed_files
    assert "out.txt" in snap.file_states
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "hi"
