import asyncio
import logging
import os

from opcode_cli.team.backends.base import Backend, BackendHandle

logger = logging.getLogger(__name__)


class ITerm2Backend(Backend):
    """在 iTerm2 窗格中运行成员进程。"""

    async def spawn(self, command: str, member_name: str) -> BackendHandle:
        escaped_command = command.replace('"', '\\"')
        script = (
            f'tell application "iTerm2"'
            f'\n  tell current session of current window'
            f'\n    tell (split vertically with default profile command "'
            f'{escaped_command}'
            f'") to select'
            f'\n  end tell'
            f'\nend tell'
        )
        proc = await asyncio.create_subprocess_shell(
            f'osascript -e "{script}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()

        logger.info("iTerm2 pane spawned for '%s'", member_name)
        return BackendHandle(
            id=member_name,
            backend_type="iterm2",
            pane_id=member_name,  # iTerm2 不直接暴露 pane_id，用名称标识
            pid=proc.pid,
        )

    async def kill(self, handle: BackendHandle) -> None:
        # iTerm2 关闭分屏较复杂，发送 exit 命令
        script = (
            'tell application "iTerm2"'
            '\n  tell current session of current window'
            f'\n    write text "exit"'
            '\n  end tell'
            '\nend tell'
        )
        await asyncio.create_subprocess_shell(
            f'osascript -e "{script}"',
        )
        logger.info("iTerm2 pane exit sent for '%s'", handle.id)

    async def is_available(self) -> bool:
        return bool(os.environ.get("ITERM_SESSION_ID"))

    async def wake(self, handle: BackendHandle) -> None:
        # iTerm2 窗格天然接收输入，无需显式唤醒
        pass
