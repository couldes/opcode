from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class BackendHandle:
    """后端返回的成员运行句柄。"""
    id: str
    backend_type: str  # "tmux" | "iterm2" | "in-process"
    pane_id: str = ""
    pid: int = 0


class Backend(ABC):
    """成员运行后端抽象基类。"""

    @abstractmethod
    async def spawn(self, command: str, member_name: str) -> BackendHandle:
        """在独立环境中启动成员进程/协程。"""
        ...

    @abstractmethod
    async def kill(self, handle: BackendHandle) -> None:
        """终止成员运行环境。"""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """检查此后端在当前环境中是否可用。"""
        ...

    @abstractmethod
    async def wake(self, handle: BackendHandle) -> None:
        """唤醒目标成员（独立进程需发信号刷新终端）。"""
        ...
