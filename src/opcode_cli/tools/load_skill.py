from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class LoadSkillParams(BaseModel):
    name: str
    params: dict | None = None


class LoadSkillTool(Tool):
    """加载并激活一个 Skill（系统级，不受白名单约束）。"""

    name = "load_skill"
    description = (
        "Load and activate a skill by name. "
        "Skills provide reusable AI operation templates. "
        "After loading, the skill's instructions and tools become available."
    )
    params_model = LoadSkillParams
    category = ToolCategory.COMMAND
    is_system_tool = True
    should_defer = True

    def __init__(
        self,
        skills_manager: object,
        command_registry: object | None = None,
        agent: object | None = None,
    ) -> None:
        self._manager = skills_manager
        self._command_registry = command_registry
        self._agent = agent

    async def execute(self, params: LoadSkillParams, working_dir: str | None = None) -> ToolResult:
        result = await self._manager.activate(params.name, self._command_registry, self._agent)
        return ToolResult(success=True, content=result)
