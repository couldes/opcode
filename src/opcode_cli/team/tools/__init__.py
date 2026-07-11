from collections.abc import Callable
from pathlib import Path

from opcode_cli.team.mailbox import Mailbox
from opcode_cli.team.registry import NameRegistry
from opcode_cli.team.task_board import TaskBoard
from opcode_cli.team.tools.task_add import TeamTaskAddTool
from opcode_cli.team.tools.task_list import TeamTaskListTool
from opcode_cli.team.tools.task_update import TeamTaskUpdateTool
from opcode_cli.team.tools.task_delete import TeamTaskDeleteTool
from opcode_cli.team.tools.msg_send import TeamMsgSendTool
from opcode_cli.team.tools.msg_read import TeamMsgReadTool
from opcode_cli.team.tools.msg_broadcast import TeamMsgBroadcastTool
from opcode_cli.team.tools.terminate import TeamTerminateTool
from opcode_cli.team.tools.merge_trigger import TeamMergeTool
from opcode_cli.team.tools.team_create import TeamCreateTool
from opcode_cli.team.tools.team_spawn import TeamSpawnTool
from opcode_cli.tools.registry import ToolRegistry


def register_team_tools(
    registry: ToolRegistry,
    task_board: TaskBoard,
    mailbox_factory: Callable[[str], Mailbox],
    own_mailbox: Mailbox,
    name_registry: NameRegistry,
    sender_name: str,
    member_runner: object | None = None,
    merge_manager: object | None = None,
    wake_callback: Callable[[str], None] | None = None,
) -> None:
    """向 registry 注册所有团队协作工具（队员和 Lead 通用）。"""

    registry.register(TeamTaskAddTool(task_board))
    registry.register(TeamTaskListTool(task_board))
    registry.register(TeamTaskUpdateTool(task_board))
    registry.register(TeamTaskDeleteTool(task_board))
    registry.register(TeamMsgSendTool(sender_name, mailbox_factory, name_registry, wake_callback))
    registry.register(TeamMsgReadTool(own_mailbox))
    registry.register(TeamMsgBroadcastTool(sender_name, mailbox_factory, name_registry, wake_callback))

    if member_runner is not None:
        registry.register(TeamTerminateTool(member_runner))
    if merge_manager is not None:
        registry.register(TeamMergeTool(merge_manager))


def register_lead_tools(
    registry: ToolRegistry,
    team_manager,
    member_runner,
    role_repo,
    worktree_manager: object | None = None,
    project_root: str = "",
) -> None:
    """向 Lead 的 registry 注册团队管理专属工具。"""
    registry.register(TeamCreateTool(team_manager))
    registry.register(TeamSpawnTool(
        team_manager, member_runner, role_repo,
        worktree_manager=worktree_manager,
        project_root=project_root,
    ))


def make_mailbox_factory(mailboxes_dir: Path) -> Callable[[str], Mailbox]:
    """创建一个 mailbox_factory，给定成员名返回其 Mailbox 实例。"""
    def factory(member_name: str) -> Mailbox:
        return Mailbox(mailboxes_dir / f"{member_name}.jsonl")
    return factory


__all__ = [
    "register_team_tools",
    "register_lead_tools",
    "make_mailbox_factory",
    "TeamTaskAddTool",
    "TeamTaskListTool",
    "TeamTaskUpdateTool",
    "TeamTaskDeleteTool",
    "TeamMsgSendTool",
    "TeamMsgReadTool",
    "TeamMsgBroadcastTool",
    "TeamTerminateTool",
    "TeamMergeTool",
    "TeamCreateTool",
    "TeamSpawnTool",
]
