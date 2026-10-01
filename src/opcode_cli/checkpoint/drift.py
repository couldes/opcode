from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from opcode_cli.checkpoint.types import CheckpointSnapshot, FileState


@dataclass
class DriftedFile:
    path: str
    reason: str  # "modified" | "deleted"
    snapshot_state: FileState | None = None
    current_state: FileState | None = None


def compute_file_state(path: Path) -> FileState | None:
    """mtime/size/sha256；文件不可读或不存在返回 None。"""
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return None
    sha = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
    except OSError:
        return None
    return FileState(
        path=str(p.resolve()),
        mtime=st.st_mtime,
        size=st.st_size,
        sha256=sha.hexdigest(),
    )


def detect_drift(snapshot: CheckpointSnapshot, project_root: Path) -> list[DriftedFile]:
    drifted: list[DriftedFile] = []
    root = Path(project_root)
    for rel, state in snapshot.file_states.items():
        p = Path(rel)
        if not p.is_absolute():
            p = root / p
        cur = compute_file_state(p)
        if cur is None:
            drifted.append(DriftedFile(path=rel, reason="deleted", snapshot_state=state))
        elif cur.sha256 != state.sha256 or cur.size != state.size or cur.mtime != state.mtime:
            drifted.append(DriftedFile(path=rel, reason="modified", snapshot_state=state, current_state=cur))
    return drifted
