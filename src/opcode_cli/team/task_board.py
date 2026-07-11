import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from opcode_cli.team.types import TeamTask

logger = logging.getLogger(__name__)

_LOCK_RETRIES = 3
_LOCK_RETRY_DELAY = 0.05
_LOCK_STALE_SECONDS = 30


class TaskBoard:
    """共享任务列表 CRUD，JSON 文件持久化。"""

    def __init__(self, tasks_path: Path):
        self._path = tasks_path

    def _lock_path(self) -> Path:
        return self._path.with_suffix(self._path.suffix + ".lock")

    def _acquire_lock(self) -> bool:
        lock_path = self._lock_path()
        for _ in range(_LOCK_RETRIES):
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w") as f:
                    json.dump({"pid": os.getpid(), "acquired_at": time.time()}, f)
                return True
            except FileExistsError:
                try:
                    with open(lock_path, "r") as f:
                        data = json.load(f)
                    lock_age = time.time() - data.get("acquired_at", 0)
                    if lock_age > _LOCK_STALE_SECONDS:
                        os.remove(lock_path)
                        continue
                    # check if pid is alive
                    try:
                        os.kill(data.get("pid", 0), 0)
                    except OSError:
                        os.remove(lock_path)
                        continue
                except (json.JSONDecodeError, FileNotFoundError):
                    try:
                        os.remove(lock_path)
                    except FileNotFoundError:
                        pass
                    continue
                time.sleep(_LOCK_RETRY_DELAY)
        return False

    def _release_lock(self) -> None:
        try:
            os.remove(self._lock_path())
        except FileNotFoundError:
            pass

    def _read_all(self) -> list[TeamTask]:
        if not self._path.exists():
            return []
        with open(self._path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return [TeamTask(**item) for item in raw]

    def _write_all(self, tasks: list[TeamTask]) -> None:
        if not self._acquire_lock():
            raise RuntimeError(f"Failed to acquire lock for {self._path}")
        try:
            raw = []
            for t in tasks:
                d = {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status,
                    "priority": t.priority,
                    "assigned_to": t.assigned_to,
                    "depends_on": t.depends_on,
                    "created_by": t.created_by,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }
                raw.append(d)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)
        finally:
            self._release_lock()

    def add(self, task: TeamTask) -> str:
        now = datetime.now(timezone.utc).isoformat()
        task.task_id = task.task_id or str(uuid.uuid4())[:8]
        task.created_at = task.created_at or now
        task.updated_at = now
        tasks = self._read_all()
        tasks.append(task)
        self._write_all(tasks)
        logger.debug("Task '%s' added: %s", task.title, task.task_id)
        return task.task_id

    def list_all(
        self,
        status: str | None = None,
        assignee: str | None = None,
        priority: str | None = None,
    ) -> list[TeamTask]:
        tasks = self._read_all()
        if status is not None:
            tasks = [t for t in tasks if t.status == status]
        if assignee is not None:
            tasks = [t for t in tasks if t.assigned_to == assignee]
        if priority is not None:
            tasks = [t for t in tasks if t.priority == priority]
        return tasks

    def update(self, task_id: str, **fields) -> bool:
        tasks = self._read_all()
        for t in tasks:
            if t.task_id == task_id:
                for key, value in fields.items():
                    if hasattr(t, key):
                        setattr(t, key, value)
                t.updated_at = datetime.now(timezone.utc).isoformat()
                self._write_all(tasks)
                return True
        return False

    def delete(self, task_id: str) -> bool:
        tasks = self._read_all()
        new_tasks = [t for t in tasks if t.task_id != task_id]
        if len(new_tasks) == len(tasks):
            return False
        self._write_all(new_tasks)
        return True
