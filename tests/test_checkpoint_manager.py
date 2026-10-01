from pathlib import Path

from opcode_cli.checkpoint.manager import CheckpointManager
from opcode_cli.checkpoint.types import CheckpointSnapshot
from opcode_cli.provider.message import Message


class _FakeAgent:
    def __init__(self, task_input: str, messages: list[Message]):
        self._task_input = task_input
        self.messages = messages


def _agent(task_input: str = "task") -> _FakeAgent:
    return _FakeAgent(task_input, [Message(role="user", content=task_input)])


def test_interval_behavior(tmp_path: Path):
    mgr = CheckpointManager(tmp_path, tmp_path, "r1", interval=2)
    assert mgr.maybe_checkpoint(_agent(), iteration=1) is None  # 1 % 2 != 0 → 跳过
    p2 = mgr.maybe_checkpoint(_agent(), iteration=2)
    assert p2 is not None
    assert p2.name == "r1_2.json"
    assert mgr.latest_snapshot() is not None
    assert mgr.latest_snapshot().iteration == 2


def test_force_checkpoint(tmp_path: Path):
    mgr = CheckpointManager(tmp_path, tmp_path, "r2", interval=10)
    assert mgr.maybe_checkpoint(_agent(), iteration=1) is None
    p = mgr.maybe_checkpoint(_agent(), iteration=1, force=True)
    assert p is not None
    assert p.name == "r2_1.json"


def test_disabled(tmp_path: Path):
    mgr = CheckpointManager(tmp_path, tmp_path, "r3", enabled=False)
    assert mgr.maybe_checkpoint(_agent(), iteration=1, force=True) is None
    assert list(tmp_path.glob("*.json")) == []


def test_captures_task_input_and_messages(tmp_path: Path):
    mgr = CheckpointManager(tmp_path, tmp_path, "r4", interval=1)
    mgr.maybe_checkpoint(_agent("my task"), iteration=1)
    snap = mgr.latest_snapshot()
    assert snap is not None
    assert snap.task_input == "my task"
    assert snap.messages[0]["role"] == "user"
