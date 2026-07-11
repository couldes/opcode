import asyncio
import logging
from collections.abc import AsyncIterator

from opcode_cli.agent.agent import Agent
from opcode_cli.agent.events import DoneEvent, ErrorEvent, SubAgentResultEvent
from opcode_cli.subagent.filter import build_sub_registry
from opcode_cli.subagent.repo import RoleRepository
from opcode_cli.subagent.task_manager import BackgroundTaskManager
from opcode_cli.subagent.types import AgentRole
from opcode_cli.permission.checker import PermissionChecker
from opcode_cli.provider.base import BaseProvider, Message, ToolCall
from opcode_cli.tools.base import ToolResult
from opcode_cli.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_FOREGROUND_TIMEOUT = 120  # 前台超时自动转后台的秒数


class SubAgentRunner:
    """创建并运行子 Agent，处理 Defined/Fork 和 foreground/background 分流。"""

    def __init__(
        self,
        provider: BaseProvider,
        base_registry: ToolRegistry,
        role_repo: RoleRepository,
        task_manager: BackgroundTaskManager,
        result_queue: asyncio.Queue,
        permission_checker: PermissionChecker | None = None,
        hook_runner: object | None = None,
        project_root: str = "",
    ):
        self._provider = provider
        self._base_registry = base_registry
        self._role_repo = role_repo
        self._task_manager = task_manager
        self._result_queue = result_queue
        self._permission_checker = permission_checker
        self._hook_runner = hook_runner
        self._project_root = project_root

        # 引用父 Agent 的 messages（由外部设置，Fork 模式需要）
        self._parent_messages: list[Message] = []

    def set_parent_messages(self, messages: list[Message]) -> None:
        """更新父 Agent 当前消息列表的引用（每次调用 agent 工具前更新）。"""
        self._parent_messages = messages

    async def run_foreground(
        self, agent_name: str, task: str,
    ) -> ToolResult:
        """前台阻塞运行 Defined 子 Agent。"""
        try:
            role = self._role_repo.get(agent_name)
        except KeyError:
            return ToolResult(
                success=False, content="",
                error=f"agent role not found: '{agent_name}'",
            )

        sub_agent = self._build_defined_agent(role)

        try:
            final_output = ""
            async for event in sub_agent.run(task):
                if isinstance(event, DoneEvent):
                    final_output = event.content
                elif isinstance(event, ErrorEvent):
                    return ToolResult(
                        success=False, content="",
                        error=event.message,
                    )
            return ToolResult(success=True, content=final_output)
        except Exception as e:
            return ToolResult(
                success=False, content="",
                error=f"sub-agent error: {e}",
            )

    async def run_background(
        self, type: str, agent_name: str | None, task: str,
    ) -> ToolResult:
        """后台异步运行子 Agent，支持 Defined 和 Fork。"""
        if type == "fork":
            sub_agent = self._build_fork_agent()
            display_name = "fork"
        else:
            try:
                role = self._role_repo.get(agent_name)  # type: ignore[arg-type]
            except KeyError:
                return ToolResult(
                    success=False, content="",
                    error=f"agent role not found: '{agent_name}'",
                )
            sub_agent = self._build_defined_agent(role)
            display_name = agent_name  # type: ignore[assignment]

        task_id = self._task_manager.create(display_name)
        self._task_manager.update(task_id, status="running")

        asyncio.create_task(
            self._run_and_capture(task_id, sub_agent, task)
        )

        return ToolResult(
            success=True,
            content=f"Background task started: {task_id}",
        )

    def _build_defined_agent(self, role: AgentRole) -> Agent:
        """构建 Defined 子 Agent：空白对话 + 受限工具 + 角色系统提示。"""
        sub_registry = build_sub_registry(self._base_registry, role, block_agent_tool=True)

        sub_permission = None
        if role.permission_mode != "inherit" and self._project_root:
            from opcode_cli.permission.mode import PermissionMode
            try:
                mode = PermissionMode(role.permission_mode)
            except ValueError:
                mode = PermissionMode.DEFAULT
            sub_permission = PermissionChecker(
                project_root=self._project_root,
                mode=mode,
                registry=sub_registry,
            )
        else:
            sub_permission = self._permission_checker

        return Agent(
            provider=self._provider,
            registry=sub_registry,
            max_iterations=role.max_turns,
            system_prompt_override=role.system_prompt,
            permission_checker=sub_permission,
            sub_agent_result_queue=self._result_queue,
            hook_runner=self._hook_runner,
        )

    def _build_fork_agent(self) -> Agent:
        """构建 Fork 子 Agent：继承父对话历史 + 同工具集。"""
        return Agent(
            provider=self._provider,
            registry=self._base_registry,
            initial_messages=list(self._parent_messages),
            permission_checker=self._permission_checker,
            sub_agent_result_queue=self._result_queue,
            hook_runner=self._hook_runner,
        )

    async def _run_and_capture(
        self, task_id: str, sub_agent: Agent, task: str,
    ) -> None:
        """后台执行子 Agent 并捕获结果。"""
        try:
            final_output = ""
            input_tokens = 0
            output_tokens = 0

            async for event in sub_agent.run(task):
                if isinstance(event, DoneEvent):
                    final_output = event.content
                elif isinstance(event, ErrorEvent):
                    self._task_manager.update(
                        task_id, status="failed", error=event.message,
                    )
                    return
                # TokenUsageEvent 会被 sub_agent 内部 yield，但我们无法直接访问
                # 子 Agent 的 _tracker。从 sub_agent 的 tracker 获取最终值。

            # 从 sub_agent 的 tracker 获取 token 统计
            if hasattr(sub_agent, '_tracker'):
                summary = sub_agent._tracker.summary
                input_tokens = summary.get("total_input_tokens", 0)
                # output_tokens 不由 CacheTracker 跟踪，保持默认为 0

            self._task_manager.update(
                task_id,
                status="completed",
                result=final_output,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            logger.warning("Sub-agent %s failed: %s", task_id, e)
            self._task_manager.update(
                task_id, status="failed", error=str(e),
            )
