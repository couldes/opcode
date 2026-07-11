from opcode_cli.team.task_board import TaskBoard
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamTaskUpdateTool(BaseTool):
    """更新共享任务字段。"""

    name = "team_task_update"
    read_only = False
    description = (
        "Update a shared task's fields. Pass the task ID and any fields to change: "
        "title, description, status, priority, assigned_to, depends_on."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Task ID to update.",
            },
            "title": {"type": "string", "description": "New title."},
            "description": {"type": "string", "description": "New description."},
            "status": {
                "type": "string",
                "enum": ["todo", "in_progress", "done", "blocked"],
                "description": "New status.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "New priority.",
            },
            "assigned_to": {"type": "string", "description": "New assignee."},
            "depends_on": {
                "type": "array",
                "items": {"type": "string"},
                "description": "New dependency list.",
            },
        },
        "required": ["task_id"],
    }

    def __init__(self, task_board: TaskBoard):
        super().__init__()
        self._board = task_board

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        task_id = kwargs["task_id"]
        updates = {}
        for field in ("title", "description", "status", "priority", "assigned_to", "depends_on"):
            if field in kwargs and kwargs[field] is not None:
                updates[field] = kwargs[field]
        if not updates:
            return ToolResult(success=False, content="", error="No fields to update.")
        ok = self._board.update(task_id, **updates)
        if not ok:
            return ToolResult(success=False, content="", error=f"Task not found: {task_id}")
        return ToolResult(success=True, content=f"Task {task_id} updated.")
