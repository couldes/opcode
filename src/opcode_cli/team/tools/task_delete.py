from opcode_cli.team.task_board import TaskBoard
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamTaskDeleteTool(BaseTool):
    """删除共享任务。"""

    name = "team_task_delete"
    read_only = False
    description = "Delete a task from the shared task list by its ID."
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "Task ID to delete."},
        },
        "required": ["task_id"],
    }

    def __init__(self, task_board: TaskBoard):
        super().__init__()
        self._board = task_board

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        ok = self._board.delete(kwargs["task_id"])
        if not ok:
            return ToolResult(success=False, content="", error=f"Task not found: {kwargs['task_id']}")
        return ToolResult(success=True, content=f"Task {kwargs['task_id']} deleted.")
