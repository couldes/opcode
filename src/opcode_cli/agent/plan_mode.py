from opcode_cli.prompt.injector import PlanModeInjector
from opcode_cli.tools.base import BaseTool
from opcode_cli.tools.registry import ToolRegistry


class PlanMode:
    def __init__(self, registry: ToolRegistry, injector: PlanModeInjector) -> None:
        self._registry = registry
        self._injector = injector
        self._in_plan = False

    @property
    def in_plan(self) -> bool:
        return self._in_plan

    @property
    def mode(self) -> str | None:
        if self._in_plan:
            return "plan"
        return None

    def start_plan(self) -> tuple[list[BaseTool], str]:
        self._in_plan = True
        tools = self._registry.get_tools_by_read_only(read_only=True)
        return tools, ""

    def start_do(self) -> tuple[list[BaseTool], str]:
        self._in_plan = False
        tools = self._registry.list_tools()
        return tools, ""

    def get_instruction(self, iteration: int) -> str | None:
        return self._injector.get_instruction(iteration, self.mode)

    def get_tools(self) -> list[BaseTool]:
        if self._in_plan:
            return self._registry.get_tools_by_read_only(read_only=True)
        return self._registry.list_tools()
