from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ToolResult:
    success: bool
    content: str
    error: str | None = None


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    parameters: dict = {}
    read_only: bool = False
    system_level: bool = False  # 系统级工具不受白名单约束

    @abstractmethod
    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        ...
