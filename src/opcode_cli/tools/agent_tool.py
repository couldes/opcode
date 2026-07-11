from opcode_cli.tools.base import BaseTool, ToolResult


class AgentTool(BaseTool):
    """子 Agent 工具 —— 主 Agent 调用此工具将子任务委派给独立子 Agent。

    通过 type 参数分流两种模式：
    - defined: 从预定义角色启动，空白对话 + 角色系统提示
    - fork: 从父对话分叉，继承完整历史 + 同工具集
    """

    name = "agent"
    read_only = False
    description = (
        "Launch a new agent to handle complex, multi-step tasks. "
        "Use 'defined' type with a named role (see available roles) for common tasks "
        "like code exploration or review. Use 'fork' type to spawn a copy of yourself "
        "with full conversation history for deep-dive analysis — fork always runs in "
        "background and reports back via system reminders."
    )
    parameters = {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["defined", "fork"],
                "description": "Sub-agent type: 'defined' uses a predefined role, "
                "'fork' inherits full conversation history.",
            },
            "agent_name": {
                "type": "string",
                "description": "Role name (required when type='defined'). "
                "Use one of the available agent roles.",
            },
            "task": {
                "type": "string",
                "description": "The task description for the sub-agent to accomplish.",
            },
            "mode": {
                "type": "string",
                "enum": ["foreground", "background"],
                "default": "foreground",
                "description": "Execution mode. 'foreground' blocks until complete "
                "(defined only). 'background' runs asynchronously (required for fork).",
            },
            "isolation": {
                "type": "string",
                "enum": ["", "worktree"],
                "default": "",
                "description": "Isolation mode. 'worktree' creates a temporary "
                "git worktree so the sub-agent works on an isolated copy of the repo.",
            },
        },
        "required": ["type", "task"],
    }

    def __init__(self):
        super().__init__()
        self._runner = None
        self._parent_messages_ref: list = []

    def set_runner(self, runner) -> None:
        self._runner = runner

    async def execute(
        self, type: str, task: str,
        agent_name: str | None = None,
        mode: str = "foreground",
        isolation: str = "",
    ) -> ToolResult:
        # 参数校验（无 runner 依赖）
        if type == "fork":
            if mode == "foreground":
                return ToolResult(
                    success=False, content="",
                    error="Fork mode requires background execution. Use mode='background'.",
                )
        elif type == "defined":
            if not agent_name:
                return ToolResult(
                    success=False, content="",
                    error="agent_name is required for defined type",
                )
        else:
            return ToolResult(
                success=False, content="",
                error=f"Unknown agent type: '{type}'. Use 'defined' or 'fork'.",
            )

        if self._runner is None:
            return ToolResult(
                success=False, content="",
                error="Agent tool not initialized: runner not set",
            )

        # 更新父 messages 引用（Fork 模式需要）
        if self._parent_messages_ref is not None:
            self._runner.set_parent_messages(list(self._parent_messages_ref))

        if type == "fork":
            return await self._runner.run_background(
                type="fork", agent_name=None, task=task, isolation=isolation,
            )

        if type == "defined":
            if mode == "background":
                return await self._runner.run_background(
                    type="defined", agent_name=agent_name, task=task, isolation=isolation,
                )
            return await self._runner.run_foreground(
                agent_name=agent_name, task=task, isolation=isolation,
            )

        # unreachable
        return ToolResult(success=False, content="", error="unreachable")
