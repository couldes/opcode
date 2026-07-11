from opcode_cli.team.task_board import TaskBoard
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamTaskListTool(BaseTool):
    """列出共享任务列表。"""

    name = "team_task_list"
    read_only = True
    description = (
        "List tasks from the shared team task list. "
        "Supports filtering by status, assignee, and priority."
    )
    parameters = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["todo", "in_progress", "done", "blocked"],
                "description": "Filter by task status.",
            },
            "assignee": {
                "type": "string",
                "description": "Filter by assigned member name.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Filter by priority.",
            },
        },
        "required": [],
    }

    def __init__(self, task_board: TaskBoard):
        super().__init__()
        self._board = task_board

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        tasks = self._board.list_all(
            status=kwargs.get("status"),
            assignee=kwargs.get("assignee"),
            priority=kwargs.get("priority"),
        )
        if not tasks:
            return ToolResult(success=True, content="No tasks found.")
        lines = []
        for t in tasks:
            deps = f" (depends: {', '.join(t.depends_on)})" if t.depends_on else ""
            lines.append(
                f"[{t.task_id}] {t.status} | {t.priority} | "
                f"assigned: {t.assigned_to or 'unassigned'} | {t.title}{deps}"
            )
        return ToolResult(success=True, content="\n".join(lines))
