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

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...
