import json
import logging
import secrets
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from opcode_cli.provider.base import Message, ToolCall
from opcode_cli.session import SessionMeta
from opcode_cli.session.types import RecordType, SessionRecord

logger = logging.getLogger(__name__)


class SessionArchiver:
    """会话消息的 JSONL 追加写和全量写。"""

    def __init__(self, sessions_dir: Path, session_id: str) -> None:
        self._dir = sessions_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id
        self._file_path = self._dir / f"{session_id}.jsonl"
        self._count = 0

    @property
    def file_path(self) -> Path:
        return self._file_path

    @property
    def message_count(self) -> int:
        return self._count

    @staticmethod
    def generate_id() -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        suffix = secrets.token_hex(2)
        return f"{ts}-{suffix}"

    def append(self, messages: list[Message]) -> None:
        with open(self._file_path, "a", encoding="utf-8") as f:
            for msg in messages:
                d = asdict(msg)
                d["tool_calls"] = _serialize_tool_calls(msg.tool_calls)
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
            f.flush()
        self._count += len(messages)

    def write_full(self, messages: list[Message]) -> None:
        self._count = 0
        with open(self._file_path, "w", encoding="utf-8") as f:
            for msg in messages:
                d = asdict(msg)
                d["tool_calls"] = _serialize_tool_calls(msg.tool_calls)
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                self._count += 1
            f.flush()

    def read(self) -> list[dict]:
        if not self._file_path.exists():
            return []
        rows = []
        with open(self._file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return rows

    def read_raw_lines(self) -> list[str]:
        if not self._file_path.exists():
            return []
        with open(self._file_path, "r", encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f if line.strip()]


def make_compact_boundary(summary: str, keep: list[Message]) -> SessionRecord:
    """创建 COMPACT_BOUNDARY 记录，内联摘要 + keep 尾部。"""
    keep_dicts = []
    for msg in keep:
        d = asdict(msg)
        d["tool_calls"] = _serialize_tool_calls(msg.tool_calls)
        keep_dicts.append(d)
    return SessionRecord(
        type=RecordType.COMPACT_BOUNDARY,
        content={"summary": summary, "keep": keep_dicts},
        timestamp=time.time(),
    )


def _serialize_tool_calls(tool_calls: list[ToolCall] | None) -> list[dict] | None:
    if tool_calls is None:
        return None
    return [{"id": tc.id, "name": tc.name, "input": tc.input} for tc in tool_calls]
