from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ToolCategory(str, Enum):
    READ = "read"
    WRITE = "write"
    COMMAND = "command"


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


class Tool(ABC):
    name: str = ""
    description: str = ""
    params_model: type[BaseModel] | None = None
    category: ToolCategory = ToolCategory.COMMAND
    is_concurrency_safe: bool = False
    is_system_tool: bool = False
    should_defer: bool = False

    @property
    def is_read_only(self) -> bool:
        return self.category == ToolCategory.READ

    def get_schema(self, fmt: str = "anthropic") -> dict:
        if self.params_model is not None:
            schema = self.params_model.model_json_schema()
        elif hasattr(self, 'parameters') and self.parameters:
            schema = self.parameters
        else:
            schema = {"type": "object", "properties": {}}
        if fmt == "anthropic":
            return {"name": self.name, "description": self.description, "input_schema": schema}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    @abstractmethod
    async def execute(self, params: BaseModel, working_dir: str | None = None) -> ToolResult:
        ...


# Backward compatibility
BaseTool = Tool
