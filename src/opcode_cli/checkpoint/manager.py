from __future__ import annotations

from pathlib import Path

from opcode_cli.checkpoint.drift import DriftedFile, detect_drift
from opcode_cli.checkpoint.store import CheckpointStore
from opcode_cli.checkpoint.types import CheckpointSnapshot


class CheckpointManager:
    def __init__(
        self,
        store_dir: Path,
        project_root: Path,
        run_id: str,
        interval: int = 1,
        enabled: bool = True,
    ) -> None:
        self._store = CheckpointStore(store_dir)
        self._project_root = Path(project_root)
        self._run_id = run_id
        self._interval = max(1, interval)
        self._enabled = enabled

    def maybe_checkpoint(
        self, agent, *, iteration: int, force: bool = False
    ) -> Path | None:
        if not self._enabled:
            return None
        if not force and iteration % self._interval != 0:
            return None
        snapshot = CheckpointSnapshot.build(
            messages=agent.messages,
            task_input=getattr(agent, "_task_input", ""),
            iteration=iteration,
            run_id=self._run_id,
            project_root=self._project_root,
            metadata={"iteration": iteration},
        )
        return self._store.save(snapshot)

    def latest_snapshot(self) -> CheckpointSnapshot | None:
        return self._store.latest(self._run_id)

    def detect_drift(self, snapshot: CheckpointSnapshot) -> list[DriftedFile]:
        return detect_drift(snapshot, self._project_root)
