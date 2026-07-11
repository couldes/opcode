import asyncio
import logging

from opcode_cli.worktree.manager import WorktreeError, WorktreeManager

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """后台定期清理过期的 Worktree 目录。"""

    def __init__(
        self,
        manager: WorktreeManager,
        ttl_seconds: float = 86400,  # 24h
        interval_seconds: float = 3600,  # 1h
    ) -> None:
        self._manager = manager
        self._ttl = ttl_seconds
        self._interval = interval_seconds
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        logger.debug("CleanupScheduler started (ttl=%ds, interval=%ds)", self._ttl, self._interval)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.debug("CleanupScheduler stopped")

    async def cleanup_once(self) -> int:
        """手动触发一次清理。返回清理数量。"""
        cleaned = 0
        try:
            expired = self._manager.list_expired(self._ttl)
        except Exception:
            logger.debug("list_expired failed", exc_info=True)
            return 0

        for entry in expired:
            git_file = entry / ".git"
            if not git_file.is_file():
                continue
            try:
                await self._manager.remove(entry, force=False)
                cleaned += 1
                logger.info("Cleaned expired worktree: %s", entry)
            except WorktreeError:
                logger.debug("Skip dirty worktree: %s", entry)
            except Exception:
                logger.warning("Failed to clean %s", entry, exc_info=True)

        return cleaned

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                count = await self.cleanup_once()
                if count > 0:
                    logger.info("CleanupScheduler removed %d worktree(s)", count)
            except asyncio.CancelledError:
                return
            except Exception:
                logger.debug("CleanupScheduler cycle error", exc_info=True)
