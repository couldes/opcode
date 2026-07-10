import json
import re
from datetime import datetime
from pathlib import Path

from opcode_cli.session import SessionMeta

_ID_PATTERN = re.compile(r"^(\d{8}-\d{6})-[0-9a-f]{4}$")


def _parse_id_from_filename(filename: str) -> tuple[str, datetime] | None:
    stem = Path(filename).stem  # 去掉 .jsonl
    m = _ID_PATTERN.match(stem)
    if not m:
        return None
    try:
        created = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return stem, created


def _count_lines(path: Path) -> int:
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for _ in f:
            count += 1
    return count


def _read_first_user_message(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if obj.get("role") == "user":
                    content = obj.get("content", "")
                    return content[:80]
            except json.JSONDecodeError:
                continue
    return "(empty)"


def _read_last_message_time(path: Path) -> datetime | None:
    last_line = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                last_line = line
    if not last_line:
        return None
    try:
        obj = json.loads(last_line)
        ts = obj.get("timestamp")
        if ts:
            return datetime.fromisoformat(ts)
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def list_sessions(sessions_dir: Path, limit: int = 10) -> list[SessionMeta]:
    """列出会话，按创建时间倒序排列。"""
    if not sessions_dir.exists():
        return []

    metas: list[SessionMeta] = []
    for file_path in sorted(sessions_dir.glob("*.jsonl"), reverse=True):
        parsed = _parse_id_from_filename(file_path.name)
        if not parsed:
            continue
        sid, created = parsed
        title = _read_first_user_message(file_path)
        count = _count_lines(file_path)
        last_time = _read_last_message_time(file_path)

        metas.append(SessionMeta(
            id=sid,
            path=file_path,
            title=title,
            message_count=count,
            created_at=created,
            last_message_at=last_time,
        ))

    metas.sort(key=lambda m: m.created_at, reverse=True)
    return metas[:limit]


def get_session_meta(sessions_dir: Path, session_id: str) -> SessionMeta | None:
    file_path = sessions_dir / f"{session_id}.jsonl"
    if not file_path.exists():
        return None

    parsed = _parse_id_from_filename(file_path.name)
    if not parsed:
        return None
    sid, created = parsed
    title = _read_first_user_message(file_path)
    count = _count_lines(file_path)
    last_time = _read_last_message_time(file_path)

    return SessionMeta(
        id=sid,
        path=file_path,
        title=title,
        message_count=count,
        created_at=created,
        last_message_at=last_time,
    )


def session_exists(sessions_dir: Path, session_id: str) -> bool:
    return (sessions_dir / f"{session_id}.jsonl").exists()
