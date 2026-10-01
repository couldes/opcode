from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from opcode_cli.provider.message import Message, ToolCall


@dataclass
class FileState:
    path: str
    mtime: float
    size: int
    sha256: str

    def to_dict(self) -> dict:
        return {"path": self.path, "mtime": self.mtime, "size": self.size, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, d: dict) -> "FileState":
        return cls(path=d["path"], mtime=d["mtime"], size=d["size"], sha256=d["sha256"])


def serialize_message(m: Message) -> dict:
    d = {"role": m.role, "content": m.content}
    if m.thinking is not None:
        d["thinking"] = m.thinking
    if m.tool_calls:
        d["tool_calls"] = [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in m.tool_calls]
    if m.tool_call_id is not None:
        d["tool_call_id"] = m.tool_call_id
    if m.name is not None:
        d["name"] = m.name
    return d


def deserialize_message(d: dict) -> Message:
    raw_tool_calls = d.get("tool_calls")
    tool_calls = None
    if raw_tool_calls:
        tool_calls = [
            ToolCall(id=t["id"], name=t["name"], input=t.get("input", {}))
            for t in raw_tool_calls
        ]
    return Message(
        role=d["role"],
        content=d.get("content", ""),
        thinking=d.get("thinking"),
        tool_calls=tool_calls,
        tool_call_id=d.get("tool_call_id"),
        name=d.get("name"),
    )


@dataclass
class CheckpointSnapshot:
    version: int = 1
    run_id: str = ""
    task_input: str = ""
    created_at: str = ""
    iteration: int = 0
    summary: str = ""
    messages: list[dict] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    file_states: dict[str, FileState] = field(default_factory=dict)
    decisions: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "task_input": self.task_input,
            "created_at": self.created_at,
            "iteration": self.iteration,
            "summary": self.summary,
            "messages": self.messages,
            "changed_files": self.changed_files,
            "file_states": {k: v.to_dict() for k, v in self.file_states.items()},
            "decisions": self.decisions,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CheckpointSnapshot":
        return cls(
            version=d.get("version", 1),
            run_id=d.get("run_id", ""),
            task_input=d.get("task_input", ""),
            created_at=d.get("created_at", ""),
            iteration=d.get("iteration", 0),
            summary=d.get("summary", ""),
            messages=d.get("messages", []),
            changed_files=d.get("changed_files", []),
            file_states={
                k: FileState.from_dict(v) for k, v in d.get("file_states", {}).items()
            },
            decisions=d.get("decisions", []),
            metadata=d.get("metadata", {}),
        )

    @classmethod
    def build(
        cls,
        *,
        messages: list[Message],
        task_input: str,
        iteration: int,
        run_id: str,
        project_root: Path,
        metadata: dict | None = None,
    ) -> "CheckpointSnapshot":
        """从会话消息提取紧凑状态：changed_files / file_states / decisions / summary。"""
        from opcode_cli.checkpoint.drift import compute_file_state

        changed_files: list[str] = []
        referenced: set[str] = set()
        decisions: list[dict] = []
        last_assistant = ""

        tool_results: dict[str, str] = {}
        for m in messages:
            if m.role == "tool" and m.tool_call_id is not None:
                tool_results[m.tool_call_id] = m.content
            elif m.role == "assistant" and m.content:
                last_assistant = m.content

        for m in messages:
            if m.role != "assistant" or not m.tool_calls:
                continue
            for tc in m.tool_calls:
                if not isinstance(tc, ToolCall):
                    continue
                path = tc.input.get("path")
                if isinstance(path, str):
                    if tc.name in ("write_file", "edit_file") and path not in changed_files:
                        changed_files.append(path)
                    referenced.add(path)
                ok = True
                if tc.id in tool_results:
                    ok = not tool_results[tc.id].startswith("Error:")
                decisions.append({"name": tc.name, "args": _summarize_args(tc.input), "ok": ok})

        file_states: dict[str, FileState] = {}
        for rel in referenced:
            abs_path = Path(rel)
            if not abs_path.is_absolute():
                abs_path = Path(project_root) / abs_path
            fs = compute_file_state(abs_path)
            if fs is not None:
                file_states[rel] = fs

        summary = last_assistant[:2000] if last_assistant else ""
        if decisions:
            summary = (summary + "\n" if summary else "") + f"[tool calls: {len(decisions)}]"

        return cls(
            version=1,
            run_id=run_id,
            task_input=task_input,
            created_at=datetime.now(timezone.utc).isoformat(),
            iteration=iteration,
            summary=summary,
            messages=[serialize_message(m) for m in messages],
            changed_files=changed_files,
            file_states=file_states,
            decisions=decisions,
            metadata=metadata or {},
        )


def _summarize_args(args: dict) -> str:
    parts = []
    for k, v in list(args.items())[:4]:
        s = str(v)
        if len(s) > 120:
            s = s[:117] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
