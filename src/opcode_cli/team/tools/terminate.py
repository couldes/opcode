from opcode_cli.tools.base import BaseTool, ToolResult


class TeamTerminateTool(BaseTool):
    """终止指定队员（Coordinator 专属）。"""

    name = "team_terminate"
    read_only = False
    description = (
        "Terminate a team member. This kills the member's process/pane "
        "and marks them offline. Only available in coordinator mode."
    )
    parameters = {
        "type": "object",
        "properties": {
            "member_name": {
                "type": "string",
                "description": "Name of the member to terminate.",
            },
        },
        "required": ["member_name"],
    }

    def __init__(self, member_runner):
        super().__init__()
        self._runner = member_runner

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        name = kwargs["member_name"]
        try:
            await self._runner.kill_by_name(name)
            return ToolResult(success=True, content=f"Member '{name}' terminated.")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
