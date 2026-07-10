from __future__ import annotations

from opcode_cli.tools.base import BaseTool, ToolResult


class LoadSkillTool(BaseTool):
    """加载并激活一个 Skill（系统级，不受白名单约束）。"""

    name = "load_skill"
    description = (
        "Load and activate a skill by name. "
        "Skills provide reusable AI operation templates. "
        "After loading, the skill's instructions and tools become available."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name to load",
            },
            "params": {
                "type": "object",
                "description": "Optional parameter values to fill placeholders in the skill content",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["name"],
    }
    system_level: bool = True

    def __init__(
        self,
        skills_manager: object,
        command_registry: object | None = None,
        agent: object | None = None,
    ) -> None:
        self._manager = skills_manager
        self._command_registry = command_registry
        self._agent = agent

    async def execute(self, name: str, params: dict | None = None) -> ToolResult:
        result = await self._manager.activate(name, self._command_registry, self._agent)
        return ToolResult(success=True, content=result)
