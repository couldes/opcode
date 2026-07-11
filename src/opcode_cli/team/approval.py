import logging

from opcode_cli.team.mailbox import Mailbox
from opcode_cli.team.types import MailboxMessage, MemberInfo

logger = logging.getLogger(__name__)


class ApprovalGuard:
    """审批流——审批请求构造、批复解析、写工具拦截。"""

    def __init__(self, member_name: str, lead_name: str, mailbox: Mailbox):
        self._member = member_name
        self._lead = lead_name
        self._mailbox = mailbox
        self._pending_msg_id: str | None = None
        self.approval_status: str = "none"  # none | pending | approved | rejected | approved_with_conditions
        self.approval_comments: str = ""
        self.approval_conditions: list[str] = []

    @staticmethod
    def needs_approval(member_info: MemberInfo) -> bool:
        return member_info.needs_approval

    async def request_approval(
        self,
        plan_summary: str,
        task_ids: list[str],
        send_callback,
    ) -> str:
        """发送审批请求。send_callback 是向 Lead 发消息的函数。"""
        msg_id = await send_callback(
            to=self._lead,
            body=f"Approval request from {self._member}:\n\n{plan_summary}",
            protocol="approval_request",
            extra={
                "plan_summary": plan_summary,
                "task_ids": task_ids,
                "from_member": self._member,
            },
        )
        self._pending_msg_id = msg_id
        self.approval_status = "pending"
        logger.info("Approval requested by '%s', msg_id=%s", self._member, msg_id)
        return msg_id

    def check_approval_status(self) -> str:
        """轮询邮箱检查是否有针对最新审批请求的回复。"""
        if self.approval_status != "pending":
            return self.approval_status

        msgs = self._mailbox.read_all(unread_only=True, sender=self._lead)
        for msg in msgs:
            if msg.protocol != "approval_response":
                continue
            # 检查是否回复给我们的审批请求
            reply_to = msg.extra.get("reply_to", "")
            if reply_to != self._pending_msg_id and self._pending_msg_id is not None:
                continue
            decision = msg.extra.get("decision", "rejected")
            self.approval_status = decision
            self.approval_comments = msg.extra.get("comments", "")
            self.approval_conditions = msg.extra.get("conditions", [])
            self._mailbox.mark_read(msg.msg_id)
            logger.info(
                "Approval response for '%s': %s (comments: %s)",
                self._member, decision, self.approval_comments,
            )
            break

        return self.approval_status

    def wrap_write_tools(self, registry):
        """包装 write_file/edit_file 工具，执行前检查审批状态。

        对于 needs_approval 的成员，若状态不是 approved/approved_with_conditions，
        则拦截写操作并返回 error。
        """
        return _ApprovalWrappedRegistry(registry, self)


class _ApprovalWrappedRegistry:
    """代理 ToolRegistry，对写工具注入审批检查。"""

    _WRITE_TOOLS = {"write_file", "edit_file"}

    def __init__(self, inner, guard: ApprovalGuard):
        self._inner = inner
        self._guard = guard

    def get(self, name: str):
        return self._inner.get(name)

    def remove(self, name: str) -> None:
        self._inner.remove(name)

    def list_tools(self):
        return self._inner.list_tools()

    def get_tools_by_read_only(self, read_only: bool):
        return self._inner.get_tools_by_read_only(read_only)

    def to_anthropic_format(self):
        return self._inner.to_anthropic_format()

    def to_openai_format(self):
        return self._inner.to_openai_format()

    def register(self, tool) -> None:
        self._inner.register(tool)

    async def execute(self, name: str, working_dir: str | None = None, **kwargs):
        if name in self._WRITE_TOOLS:
            status = self._guard.check_approval_status()
            if status == "none" or status == "pending":
                from opcode_cli.tools.base import ToolResult
                return ToolResult(
                    success=False, content="",
                    error=(
                        "Approval required before writing files. "
                        "Send an approval_request to the Lead first via team_msg_send "
                        "with protocol='approval_request'. "
                        f"Current status: {status}."
                    ),
                )
            if status == "rejected":
                from opcode_cli.tools.base import ToolResult
                return ToolResult(
                    success=False, content="",
                    error=(
                        "Your plan was rejected. "
                        f"Lead comments: {self._guard.approval_comments}. "
                        "Revise your plan and send a new approval_request."
                    ),
                )
            # approved or approved_with_conditions — proceed
        return await self._inner.execute(name, working_dir=working_dir, **kwargs)
