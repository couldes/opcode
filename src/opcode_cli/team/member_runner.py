import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from opcode_cli.agent.agent import Agent
from opcode_cli.subagent.filter import build_sub_registry
from opcode_cli.subagent.repo import RoleRepository
from opcode_cli.team.backends import detect_backend, get_backend, InProcessBackend
from opcode_cli.team.backends.base import BackendHandle
from opcode_cli.team.manager import TeamManager
from opcode_cli.team.mailbox import Mailbox
from opcode_cli.team.registry import NameRegistry
from opcode_cli.team.task_board import TaskBoard
from opcode_cli.team.tools import make_mailbox_factory, register_team_tools
from opcode_cli.team.types import MemberContext, MemberInfo, TeamConfig

logger = logging.getLogger(__name__)


class MemberRunner:
    """成员生命周期管理——派生、上下文持久化、恢复、终止。"""

    def __init__(
        self,
        provider,
        base_registry,
        role_repo: RoleRepository,
        teams_base: Path,
        hook_runner: object | None = None,
        worktree_manager: object | None = None,
        permission_checker: object | None = None,
    ):
        self._provider = provider
        self._base_registry = base_registry
        self._role_repo = role_repo
        self._teams_base = teams_base
        self._hook_runner = hook_runner
        self._worktree_manager = worktree_manager
        self._permission_checker = permission_checker
        self._in_process_backend = InProcessBackend()
        self._active_handles: dict[str, BackendHandle] = {}

    async def spawn(
        self,
        config: TeamConfig,
        member_info: MemberInfo,
        task: str,
        backend_type: str | None = None,
    ) -> BackendHandle:
        """派生成员。若未指定 backend，自动检测。"""
        if backend_type is None:
            backend_type = await detect_backend()

        member_info.backend = backend_type
        backend = get_backend(backend_type)

        if backend_type == "in-process":
            handle = await self._spawn_in_process(config, member_info, task)
        else:
            command = self._build_member_command(config.name, member_info.name, backend_type)
            handle = await backend.spawn(command, member_info.name)

        self._active_handles[member_info.name] = handle
        member_info.status = "active"

        # 更新运行时注册表
        runtime_path = config.root_dir / "runtime.json"
        registry = NameRegistry(config.root_dir / "roster.json", runtime_path)
        registry.set_online(member_info.name, backend_type, handle.pane_id)

        logger.info("Member '%s' spawned with backend '%s'", member_info.name, backend_type)
        return handle

    async def resume(
        self,
        config: TeamConfig,
        member_name: str,
        task: str,
    ) -> BackendHandle:
        """从磁盘恢复成员上下文后继续指派。"""
        member_info = config.members.get(member_name)
        if member_info is None:
            raise ValueError(f"Member not found: '{member_name}'")

        ctx = await self.load_context(member_name, config.root_dir)
        backend_type = member_info.backend or "in-process"

        if backend_type == "in-process":
            handle = await self._spawn_in_process(config, member_info, task, ctx)
        else:
            command = self._build_member_command(config.name, member_name, backend_type)
            backend = get_backend(backend_type)
            handle = await backend.spawn(command, member_name)

        self._active_handles[member_name] = handle
        member_info.status = "active"

        # 更新运行时
        runtime_path = config.root_dir / "runtime.json"
        registry = NameRegistry(config.root_dir / "roster.json", runtime_path)
        registry.set_online(member_name, backend_type)

        logger.info("Member '%s' resumed with backend '%s'", member_name, backend_type)
        return handle

    async def kill_by_name(self, member_name: str) -> None:
        """按名称终止成员。"""
        handle = self._active_handles.pop(member_name, None)
        if handle is None:
            raise ValueError(f"No active handle for member: '{member_name}'")

        backend = get_backend(handle.backend_type)
        await backend.kill(handle)

        logger.info("Member '%s' killed", member_name)

    async def save_context(self, member_name: str, agent: Agent, team_dir: Path) -> None:
        """序列化成员上下文到磁盘。"""
        context_dir = team_dir / "context"
        context_dir.mkdir(parents=True, exist_ok=True)

        tracker_summary = {}
        if hasattr(agent, '_tracker'):
            tracker_summary = dict(agent._tracker.summary)

        raw_messages = []
        for msg in agent.messages:
            if hasattr(msg, 'role') and hasattr(msg, 'content'):
                raw_messages.append({"role": msg.role, "content": msg.content})
            elif isinstance(msg, dict):
                raw_messages.append(msg)
            else:
                raw_messages.append({"role": "unknown", "content": str(msg)})

        ctx = MemberContext(
            member_name=member_name,
            messages=raw_messages,
            tracker_summary=tracker_summary,
            serialized_at=datetime.now(timezone.utc).isoformat(),
        )

        path = context_dir / f"{member_name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._context_to_dict(ctx), f, indent=2, ensure_ascii=False, default=str)

        logger.info("Context saved for '%s': %d messages", member_name, len(raw_messages))

    async def load_context(self, member_name: str, team_dir: Path) -> MemberContext | None:
        """从磁盘加载成员上下文。"""
        path = team_dir / "context" / f"{member_name}.json"
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages = []
        for m in data.get("messages", []):
            messages.append({"role": m.get("role", "user"), "content": m.get("content", "")})

        return MemberContext(
            member_name=member_name,
            messages=messages,
            tracker_summary=data.get("tracker_summary", {}),
            last_task_id=data.get("last_task_id"),
            serialized_at=data.get("serialized_at", ""),
        )

    async def _spawn_in_process(
        self,
        config: TeamConfig,
        member_info: MemberInfo,
        task: str,
        context: MemberContext | None = None,
    ) -> BackendHandle:
        """同进程派生：创建 Agent 实例并在 asyncio Task 中运行。"""
        agent = await self._build_member_agent(config, member_info, context)

        task_coro = self._run_member_loop(agent, member_info, task, config)
        asyncio_task = asyncio.create_task(task_coro)
        self._in_process_backend.register_task(member_info.name, asyncio_task)

        return BackendHandle(
            id=member_info.name,
            backend_type="in-process",
            pid=0,
        )

    def _build_member_command(self, team_name: str, member_name: str, backend_type: str) -> str:
        """构造独立进程启动命令。"""
        cwd = Path.cwd()
        return (
            f'cd "{cwd}" && '
            f'.venv/Scripts/python -m opcode_cli.main '
            f'--team "{team_name}" --member "{member_name}" --backend "{backend_type}"'
        )

    async def _build_member_agent(
        self,
        config: TeamConfig,
        member_info: MemberInfo,
        context: MemberContext | None = None,
    ) -> Agent:
        """构造队员 Agent 实例，含协作工具和审批守卫。"""
        role = self._role_repo.get(member_info.role_name)

        sub_registry = build_sub_registry(self._base_registry, role, block_agent_tool=True)

        # Worktree 隔离
        working_dir: str | None = None
        system_prompt = role.system_prompt
        if role.isolation == "worktree" and self._worktree_manager is not None:
            try:
                from opcode_cli.worktree.manager import WorktreeManager
                wm: WorktreeManager = self._worktree_manager
                info = await wm.create(role.name)
                working_dir = str(info.path)
                system_prompt = system_prompt + f"\n\nYour working directory is: {working_dir}"
                member_info.working_dir = working_dir
            except Exception as e:
                logger.warning("Failed to create worktree for '%s': %s", member_info.name, e)

        # 注册协作工具
        mailboxes_dir = config.root_dir / "mailboxes"
        mailboxes_dir.mkdir(parents=True, exist_ok=True)
        mailbox_factory = make_mailbox_factory(mailboxes_dir)
        own_mailbox = Mailbox(mailboxes_dir / f"{member_info.name}.jsonl")

        task_board = TaskBoard(config.root_dir / "tasks.json")
        name_registry = NameRegistry(
            config.root_dir / "roster.json",
            config.root_dir / "runtime.json",
        )

        register_team_tools(
            registry=sub_registry,
            task_board=task_board,
            mailbox_factory=mailbox_factory,
            own_mailbox=own_mailbox,
            name_registry=name_registry,
            sender_name=member_info.name,
        )

        # 审批守卫（若需要）
        approval_guard = None
        if member_info.needs_approval:
            from opcode_cli.team.approval import ApprovalGuard
            approval_guard = ApprovalGuard(
                member_name=member_info.name,
                lead_name=config.lead_name,
                mailbox=own_mailbox,
            )

        # 权限
        sub_permission = self._permission_checker
        if role.permission_mode != "inherit" and hasattr(self._permission_checker, 'project_root'):
            from opcode_cli.permission.mode import PermissionMode
            from opcode_cli.permission.checker import PermissionChecker
            try:
                mode = PermissionMode(role.permission_mode)
            except ValueError:
                mode = PermissionMode.DEFAULT
            sub_permission = PermissionChecker(
                project_root=self._permission_checker.project_root,  # type: ignore[union-attr]
                mode=mode,
                registry=sub_registry,
            )

        initial_messages = None
        if context and context.messages:
            from opcode_cli.provider.base import Message
            initial_messages = [Message(role=m["role"], content=m["content"]) for m in context.messages]

        context_save_path = str(config.root_dir / "context" / f"{member_info.name}.json")

        return Agent(
            provider=self._provider,
            registry=sub_registry,
            max_iterations=role.max_turns,
            system_prompt_override=system_prompt,
            permission_checker=sub_permission,
            hook_runner=self._hook_runner,
            working_dir=working_dir,
            initial_messages=initial_messages,
            team_mailbox=own_mailbox,
            team_approval_guard=approval_guard,
            team_member_name=member_info.name,
            team_lead_name=config.lead_name,
            team_context_save_path=context_save_path,
        )

    async def _run_member_loop(
        self,
        agent: Agent,
        member_info: MemberInfo,
        task: str,
        config: TeamConfig,
    ) -> None:
        """in-process 成员的 Agent 循环。"""
        try:
            from opcode_cli.agent.events import DoneEvent, ErrorEvent

            async for event in agent.run(task):
                if isinstance(event, DoneEvent):
                    member_info.status = "idle"
                    logger.info("Member '%s' completed task, now idle", member_info.name)
                    await self.save_context(member_info.name, agent, config.root_dir)

                    # 发 status_report 给 Lead
                    lead_mb = Mailbox(config.root_dir / "mailboxes" / f"{config.lead_name}.jsonl")
                    from opcode_cli.team.types import MailboxMessage
                    msg = MailboxMessage(
                        sender=member_info.name,
                        body=f"Task completed. Status: idle.",
                        protocol="status_report",
                        extra={
                            "status": "idle",
                            "from_member": member_info.name,
                        },
                    )
                    lead_mb.send(msg)
                    logger.info("Status report sent to Lead from '%s'", member_info.name)
                    return

                elif isinstance(event, ErrorEvent):
                    member_info.status = "failed"
                    logger.error("Member '%s' error: %s", member_info.name, event.message)
                    await self.save_context(member_info.name, agent, config.root_dir)
                    return

        except Exception as e:
            member_info.status = "failed"
            logger.error("Member '%s' loop crashed: %s", member_info.name, e)
            try:
                await self.save_context(member_info.name, agent, config.root_dir)
            except Exception:
                pass

    @staticmethod
    def _context_to_dict(ctx: MemberContext) -> dict:
        return {
            "member_name": ctx.member_name,
            "messages": ctx.messages,
            "tracker_summary": ctx.tracker_summary,
            "last_task_id": ctx.last_task_id,
            "serialized_at": ctx.serialized_at,
        }
