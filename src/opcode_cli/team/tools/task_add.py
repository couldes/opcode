from opcode_cli.team.task_board import TaskBoard
from opcode_cli.team.types import TeamTask
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamTaskAddTool(BaseTool):
    """向共享任务列表添加任务。"""

    name = "team_task_add"
    read_only = False
    description = (
        "Add a task to the shared team task list. "
        "Use this to create new tasks with optional dependency markers. "
        "Parameters: title (required), description, depends_on (list of task IDs), "
        "priority (low/medium/high/urgent), assigned_to."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Task title (required).",
            },
            "description": {
                "type": "string",
                "description": "Task description.",
            },
            "depends_on": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of task IDs this task depends on (markers only).",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high", "urgent"],
                "description": "Task priority. Default: medium.",
            },
            "assigned_to": {
                "type": "string",
                "description": "Name of the member assigned to this task.",
            },
        },
        "required": ["title"],
    }

    def __init__(self, task_board: TaskBoard):
        super().__init__()
        self._board = task_board

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        title = kwargs.get("title", "")
        task = TeamTask(
            title=title,
            description=kwargs.get("description", ""),
            depends_on=kwargs.get("depends_on", []),
            priority=kwargs.get("priority", "medium"),
            assigned_to=kwargs.get("assigned_to"),
        )
        task_id = self._board.add(task)
        return ToolResult(
            success=True,
            content=f"Task '{title}' added with ID: {task_id}",
        )
