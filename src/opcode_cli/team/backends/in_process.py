import asyncio
import logging

from opcode_cli.team.backends.base import Backend, BackendHandle

logger = logging.getLogger(__name__)


class InProcessBackend(Backend):
    """同进程 asyncio 协程运行成员 Agent。

    实际 Agent 循环由 MemberRunner 直接管理，此后端主要负责句柄跟踪。
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    async def spawn(self, command: str, member_name: str) -> BackendHandle:
        # in-process 不走 command 字符串；由 MemberRunner 用 asyncio.create_task 启动
        return BackendHandle(
            id=member_name,
            backend_type="in-process",
            pane_id="",
            pid=0,
        )

    async def kill(self, handle: BackendHandle) -> None:
        task = self._tasks.pop(handle.id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("In-process member '%s' cancelled", handle.id)

    async def is_available(self) -> bool:
        return True

    async def wake(self, handle: BackendHandle) -> None:
        # 协程轮询邮箱，无需唤醒
        pass

    def register_task(self, member_name: str, task: asyncio.Task) -> None:
        """将 asyncio Task 与成员名关联。"""
        self._tasks[member_name] = task
