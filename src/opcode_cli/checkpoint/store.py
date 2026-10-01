from __future__ import annotations

import json
import os
from pathlib import Path

from opcode_cli.checkpoint.types import CheckpointSnapshot


class CheckpointStore:
    def __init__(self, dir: Path) -> None:
        self._dir = Path(dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: CheckpointSnapshot) -> Path:
        path = self._dir / f"{snapshot.run_id}_{snapshot.iteration}.json"
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, ensure_ascii=False)
        os.replace(tmp, path)
        return path

    def latest(self, run_id: str) -> CheckpointSnapshot | None:
        prefix = f"{run_id}_"
        best: Path | None = None
        best_iter = -1
        for p in self._dir.glob(f"{run_id}_*.json"):
            name = p.stem[len(prefix):]
            try:
                it = int(name)
            except ValueError:
                continue
            if it > best_iter:
                best_iter = it
                best = p
        return self.load(best) if best is not None else None

    def load(self, path: Path) -> CheckpointSnapshot:
        with open(path, "r", encoding="utf-8") as f:
            return CheckpointSnapshot.from_dict(json.load(f))
