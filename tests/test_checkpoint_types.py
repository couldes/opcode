from pathlib import Path

from opcode_cli.checkpoint.types import CheckpointSnapshot, deserialize_message, serialize_message
from opcode_cli.provider.message import Message, ToolCall


def _messages(project_root: Path) -> list[Message]:
    calc = project_root / "calc.py"
    calc.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    return [
        Message(role="user", content="fix the bug"),
        Message(
            role="assistant",
            content="let me read calc.py",
            tool_calls=[ToolCall(id="c1", name="read_file", input={"path": str(calc)})],
        ),
        Message(role="tool", content="def add(a, b):\n    return a + b\n", tool_call_id="c1", name="read_file"),
        Message(
            role="assistant",
            content="editing",
            tool_calls=[ToolCall(id="c2", name="write_file", input={"path": str(calc), "content": "fixed"})],
        ),
        Message(role="tool", content="written", tool_call_id="c2", name="write_file"),
    ]


def test_build_extracts_state(tmp_path: Path):
    snap = CheckpointSnapshot.build(
        messages=_messages(tmp_path),
        task_input="fix the bug",
        iteration=2,
        run_id="r1",
        project_root=tmp_path,
    )
    assert snap.task_input == "fix the bug"
    assert snap.iteration == 2
    assert snap.changed_files == [str(tmp_path / "calc.py")]
    # read_file + write_file 两个引用路径都进了 file_states
    assert str(tmp_path / "calc.py") in snap.file_states
    # decisions: read 成功、write 成功
    assert [d["name"] for d in snap.decisions] == ["read_file", "write_file"]
    assert all(d["ok"] for d in snap.decisions)
    assert "tool calls: 2" in snap.summary
    assert len(snap.messages) == len(_messages(tmp_path))


def test_build_marks_failed_tool_call(tmp_path: Path):
    msgs = [
        Message(role="user", content="go"),
        Message(
            role="assistant",
            content="edit",
            tool_calls=[ToolCall(id="x", name="write_file", input={"path": "a.py", "content": "x"})],
        ),
        Message(role="tool", content="Error: blocked", tool_call_id="x", name="write_file"),
    ]
    snap = CheckpointSnapshot.build(
        messages=msgs, task_input="go", iteration=1, run_id="r", project_root=tmp_path
    )
    assert snap.decisions[0]["ok"] is False


def test_serialize_roundtrip_with_tool_calls():
    m = Message(
        role="assistant",
        content="hi",
        thinking="think",
        tool_calls=[ToolCall(id="t1", name="grep_search", input={"pattern": "x", "path": "."})],
    )
    d = serialize_message(m)
    m2 = deserialize_message(d)
    assert m2.role == "assistant"
    assert m2.content == "hi"
    assert m2.thinking == "think"
    assert m2.tool_calls is not None
    assert m2.tool_calls[0].id == "t1"
    assert m2.tool_calls[0].name == "grep_search"
    assert m2.tool_calls[0].input == {"pattern": "x", "path": "."}


def test_snapshot_dict_roundtrip(tmp_path: Path):
    snap = CheckpointSnapshot.build(
        messages=_messages(tmp_path), task_input="t", iteration=3, run_id="r2", project_root=tmp_path
    )
    d = snap.to_dict()
    snap2 = CheckpointSnapshot.from_dict(d)
    assert snap2.run_id == snap.run_id
    assert snap2.iteration == 3
    assert snap2.changed_files == snap.changed_files
    assert list(snap2.file_states) == list(snap.file_states)
    assert snap2.messages == snap.messages
