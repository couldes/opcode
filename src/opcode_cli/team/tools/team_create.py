from opcode_cli.team.manager import TeamManager
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamCreateTool(BaseTool):
    """创建新团队（Lead 专属）。"""

    name = "team_create"
    read_only = False
    description = (
        "Create a new team. This initializes the team directory structure "
        "under ~/.opcode/teams/<name>/. "
        "Parameters: name (required, team name), lead_name (your name)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Team name, used as the persistence directory name.",
            },
            "lead_name": {
                "type": "string",
                "description": "The lead's name (your name).",
            },
        },
        "required": ["team_name", "lead_name"],
    }

    def __init__(self, team_manager: TeamManager):
        super().__init__()
        self._mgr = team_manager

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        try:
            config = self._mgr.create(kwargs["team_name"], kwargs["lead_name"])
            return ToolResult(
                success=True,
                content=f"Team '{config.name}' created at {config.root_dir}",
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
