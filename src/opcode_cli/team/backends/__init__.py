import asyncio
import logging

from opcode_cli.team.backends.base import Backend, BackendHandle
from opcode_cli.team.backends.tmux import TmuxBackend
from opcode_cli.team.backends.iterm2 import ITerm2Backend
from opcode_cli.team.backends.in_process import InProcessBackend

logger = logging.getLogger(__name__)


async def detect_backend() -> str:
    """按优先级检测可用后端：tmux → iterm2 → in-process。"""
    backends = [
        ("tmux", TmuxBackend()),
        ("iterm2", ITerm2Backend()),
        ("in-process", InProcessBackend()),
    ]
    for name, backend in backends:
        try:
            if await backend.is_available():
                logger.info("Detected backend: %s", name)
                return name
        except Exception:
            pass
        logger.debug("Backend '%s' not available", name)
    return "in-process"


def get_backend(name: str) -> Backend:
    """根据名称获取后端实例。"""
    if name == "tmux":
        return TmuxBackend()
    elif name == "iterm2":
        return ITerm2Backend()
    else:
        return InProcessBackend()


__all__ = [
    "Backend",
    "BackendHandle",
    "TmuxBackend",
    "ITerm2Backend",
    "InProcessBackend",
    "detect_backend",
    "get_backend",
]
