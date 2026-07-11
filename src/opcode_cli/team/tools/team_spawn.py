from pathlib import Path

from opcode_cli.team.manager import TeamManager
from opcode_cli.team.types import MemberInfo
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamSpawnTool(BaseTool):
    """派生队员（Lead 专属）。"""

    name = "team_spawn"
    read_only = False
    description = (
        "Spawn a new team member. Adds the member to the roster, "
        "starts the member's agent process/coroutine, and assigns an initial task. "
        "Parameters: team_name (required), member_name (required), "
        "role_name (required, e.g. 'explorer' or 'coder'), "
        "task (required, description of what the member should do), "
        "needs_approval (default false), backend (default auto)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "team_name": {
                "type": "string",
                "description": "Name of the existing team.",
            },
            "member_name": {
                "type": "string",
                "description": "Name for the new member.",
            },
            "role_name": {
                "type": "string",
                "description": "Agent role name to use (e.g. 'explorer', 'reviewer').",
            },
            "task": {
                "type": "string",
                "description": "Initial task description for the member.",
            },
            "needs_approval": {
                "type": "boolean",
                "description": "Whether this member needs Lead approval before writing files. Default: false.",
            },
            "backend": {
                "type": "string",
                "enum": ["auto", "tmux", "iterm2", "in-process"],
                "description": "Runtime backend. Default: auto-detect.",
            },
        },
        "required": ["team_name", "member_name", "role_name", "task"],
    }

    def __init__(
        self,
        team_manager: TeamManager,
        member_runner,
        role_repo,
        worktree_manager: object | None = None,
        project_root: str = "",
    ):
        super().__init__()
        self._mgr = team_manager
        self._runner = member_runner
        self._role_repo = role_repo
        self._worktree_manager = worktree_manager
        self._project_root = project_root

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        team_name = kwargs["team_name"]
        member_name = kwargs["member_name"]
        role_name = kwargs["role_name"]
        task = kwargs["task"]

        try:
            config = self._mgr.load(team_name)
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Team not found: {team_name} ({e})")

        if member_name in config.members:
            return ToolResult(
                success=False, content="",
                error=f"Member '{member_name}' already exists in team '{team_name}'",
            )

        # 解析角色以确定 working_dir
        try:
            role = self._role_repo.get(role_name)
        except KeyError:
            return ToolResult(
                success=False, content="",
                error=f"Role not found: '{role_name}'",
            )

        # 确定工作目录（worktree 隔离 vs 项目根目录）
        wd = self._project_root or str(Path.cwd())
        if role.isolation == "worktree" and self._worktree_manager is not None:
            from opcode_cli.worktree.manager import WorktreeManager
            wm: WorktreeManager = self._worktree_manager  # type: ignore[assignment]
            try:
                info = await wm.create(role.name)
                wd = str(info.path)
            except Exception as e:
                return ToolResult(
                    success=False, content="",
                    error=f"Failed to create worktree for '{member_name}': {e}",
                )

        backend = kwargs.get("backend", "auto")
        if backend == "auto":
            backend = None  # MemberRunner.spawn will auto-detect

        needs_approval = kwargs.get("needs_approval", False)

        member_info = MemberInfo(
            name=member_name,
            role_name=role_name,
            working_dir=wd,
            backend=backend or "in-process",
            needs_approval=needs_approval,
        )

        # 添加到花名册
        self._mgr.add_member(config, member_info)

        # 派生队员
        try:
            handle = await self._runner.spawn(config, member_info, task, backend_type=backend)
        except Exception as e:
            # 回滚花名册
            self._mgr.remove_member(config, member_name)
            return ToolResult(success=False, content="", error=f"Failed to spawn member: {e}")

        # 发送任务分配消息
        from opcode_cli.team.mailbox import Mailbox
        from opcode_cli.team.types import MailboxMessage
        member_mb = Mailbox(config.root_dir / "mailboxes" / f"{member_name}.jsonl")
        msg = MailboxMessage(
            sender=config.lead_name,
            body=task,
            protocol="task_assignment",
            extra={"from_lead": config.lead_name},
        )
        member_mb.send(msg)

        return ToolResult(
            success=True,
            content=(
                f"Member '{member_name}' spawned with role '{role_name}' "
                f"(backend: {handle.backend_type}, working_dir: {wd}). "
                f"Task assigned: {task[:100]}"
            ),
        )
