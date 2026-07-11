from pydantic import BaseModel

from opcode_cli.tools.base import Tool, ToolCategory, ToolResult


class AgentToolParams(BaseModel):
    type: str
    task: str
    agent_name: str | None = None
    mode: str = "foreground"
    isolation: str = ""


class AgentTool(Tool):
    """子 Agent 工具 —— 主 Agent 调用此工具将子任务委派给独立子 Agent。"""

    name = "agent"
    description = (
        "Launch a new agent to handle complex, multi-step tasks. "
        "Use 'defined' type with a named role for common tasks. "
        "Use 'fork' type to spawn a copy of yourself with full conversation history."
    )
    params_model = AgentToolParams
    category = ToolCategory.COMMAND

    def __init__(self):
        super().__init__()
        self._runner = None
        self._parent_messages_ref: list = []

    def set_runner(self, runner) -> None:
        self._runner = runner

    async def execute(self, params: AgentToolParams, working_dir: str | None = None) -> ToolResult:
        if params.type == "fork":
            if params.mode == "foreground":
                return ToolResult(
                    success=False, content="",
                    error="Fork mode requires background execution. Use mode='background'.",
                )
        elif params.type == "defined":
            if not params.agent_name:
                return ToolResult(
                    success=False, content="",
                    error="agent_name is required for defined type",
                )
        else:
            return ToolResult(
                success=False, content="",
                error=f"Unknown agent type: '{params.type}'. Use 'defined' or 'fork'.",
            )

        if self._runner is None:
            return ToolResult(
                success=False, content="",
                error="Agent tool not initialized: runner not set",
            )

        if self._parent_messages_ref is not None:
            self._runner.set_parent_messages(list(self._parent_messages_ref))

        if params.type == "fork":
            return await self._runner.run_background(
                type="fork", agent_name=None, task=params.task, isolation=params.isolation,
            )

        if params.type == "defined":
            if params.mode == "background":
                return await self._runner.run_background(
                    type="defined", agent_name=params.agent_name, task=params.task, isolation=params.isolation,
                )
            return await self._runner.run_foreground(
                agent_name=params.agent_name, task=params.task, isolation=params.isolation,
            )

        return ToolResult(success=False, content="", error="unreachable")
