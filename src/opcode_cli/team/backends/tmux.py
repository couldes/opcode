import asyncio
import logging
import os
import shutil

from opcode_cli.team.backends.base import Backend, BackendHandle

logger = logging.getLogger(__name__)


class TmuxBackend(Backend):
    """在 tmux 窗格中运行成员进程。"""

    async def spawn(self, command: str, member_name: str) -> BackendHandle:
        # 在当前 window 创建垂直分屏
        proc = await asyncio.create_subprocess_shell(
            f'tmux split-window -v "{command}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # 获取新窗格的 pane_id
        pane_proc = await asyncio.create_subprocess_shell(
            "tmux display-message -p '#{pane_id}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        pane_stdout, _ = await pane_proc.communicate()
        pane_id = pane_stdout.decode().strip()

        logger.info("Tmux pane spawned for '%s': %s", member_name, pane_id)
        return BackendHandle(
            id=member_name,
            backend_type="tmux",
            pane_id=pane_id,
            pid=proc.pid,
        )

    async def kill(self, handle: BackendHandle) -> None:
        if handle.pane_id:
            await asyncio.create_subprocess_shell(
                f"tmux kill-pane -t {handle.pane_id}",
            )
            logger.info("Tmux pane killed: %s", handle.pane_id)

    async def is_available(self) -> bool:
        if not shutil.which("tmux"):
            return False
        # 还需要在 tmux 会话内部
        return bool(os.environ.get("TMUX"))

    async def wake(self, handle: BackendHandle) -> None:
        if handle.pane_id:
            await asyncio.create_subprocess_shell(
                f"tmux send-keys -t {handle.pane_id} Enter",
            )
            logger.debug("Wake signal sent to tmux pane %s", handle.pane_id)
