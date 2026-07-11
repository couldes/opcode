from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_SNAPSHOTS_SUBDIR = ".opcode/snapshots"


@dataclass
class FileRecord:
    path: str  # relative to project root
    mtime: float
    size: int
    hash: str  # sha256 of file content


@dataclass
class Snapshot:
    id: str  # timestamp-based
    created_at: float
    files: list[FileRecord] = field(default_factory=list)

    def find_file(self, rel_path: str) -> FileRecord | None:
        for f in self.files:
            if f.path == rel_path:
                return f
        return None


class SnapshotManager:
    """Captures and manages file state snapshots across agent loop cycles.

    Each snapshot records the content hashes of project files at a point in
    time. Two consecutive snapshots can be compared to detect what changed
    during an agent loop.
    """

    def __init__(self, project_root: str | Path) -> None:
        self._root = Path(project_root).resolve()
        self._snapshot_dir = self._root / _SNAPSHOTS_SUBDIR
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._current: Snapshot | None = None
        self._history: list[Snapshot] = []

    @property
    def current(self) -> Snapshot | None:
        return self._current

    @property
    def history(self) -> list[Snapshot]:
        return list(self._history)

    def take_snapshot(self, tracked_globs: list[str] | None = None) -> Snapshot:
        """Scan project files and record state."""
        tracked = tracked_globs or ["src/**/*.py", "*.py", "*.toml", "*.cfg"]
        files: list[FileRecord] = []

        for pattern in tracked:
            for path in self._root.glob(pattern):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(self._root))
                try:
                    stat = path.stat()
                    digest = _hash_file(path)
                    files.append(FileRecord(
                        path=rel,
                        mtime=stat.st_mtime,
                        size=stat.st_size,
                        hash=digest,
                    ))
                except OSError:
                    continue

        snapshot = Snapshot(
            id=f"{int(time.time())}-{uuid.uuid4().hex[:6]}",
            created_at=time.time(),
            files=files,
        )
        self._current = snapshot
        self._history.append(snapshot)
        self._persist(snapshot)
        return snapshot

    def diff_snapshots(self, old: Snapshot, new: Snapshot) -> dict[str, list[FileRecord]]:
        """Compare two snapshots. Returns {added, removed, modified}."""
        old_map = {f.path: f for f in old.files}
        new_map = {f.path: f for f in new.files}

        added = [f for path, f in new_map.items() if path not in old_map]
        removed = [f for path, f in old_map.items() if path not in new_map]
        modified = [
            new_map[path]
            for path, new_f in new_map.items()
            if path in old_map and old_map[path].hash != new_f.hash
        ]

        return {"added": added, "removed": removed, "modified": modified}

    def diff_from_previous(self) -> dict[str, list[FileRecord]] | None:
        """Compare current snapshot with the previous one."""
        if len(self._history) < 2:
            return None
        return self.diff_snapshots(self._history[-2], self._history[-1])

    def load_snapshot(self, snapshot_id: str) -> Snapshot | None:
        """Load a persisted snapshot by id."""
        path = self._snapshot_dir / f"{snapshot_id}.json"
        if not path.exists():
            return None
        return self._load_file(path)

    def list_snapshots(self) -> list[dict]:
        """List available snapshots."""
        results: list[dict] = []
        for f in sorted(self._snapshot_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                results.append({
                    "id": data.get("id", f.stem),
                    "created_at": data.get("created_at", 0),
                    "file_count": len(data.get("files", [])),
                })
            except (json.JSONDecodeError, OSError):
                continue
        return results

    def prune(self, keep: int = 10) -> int:
        """Remove oldest snapshots beyond ``keep`` count. Returns count removed."""
        all_files = sorted(self._snapshot_dir.glob("*.json"))
        if len(all_files) <= keep:
            return 0
        removed = 0
        for f in all_files[:-keep]:
            try:
                f.unlink()
                removed += 1
            except OSError:
                continue
        return removed

    # --- Internal ---

    def _persist(self, snapshot: Snapshot) -> None:
        path = self._snapshot_dir / f"{snapshot.id}.json"
        data = {
            "id": snapshot.id,
            "created_at": snapshot.created_at,
            "files": [
                {"path": f.path, "mtime": f.mtime, "size": f.size, "hash": f.hash}
                for f in snapshot.files
            ],
        }
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("failed to persist snapshot %s: %s", snapshot.id, e)

    def _load_file(self, path: Path) -> Snapshot | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            files = [
                FileRecord(**f) for f in data.get("files", [])
            ]
            return Snapshot(
                id=data.get("id", path.stem),
                created_at=data.get("created_at", 0),
                files=files,
            )
        except (json.JSONDecodeError, OSError, TypeError) as e:
            logger.warning("failed to load snapshot %s: %s", path, e)
            return None


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()[:32]
