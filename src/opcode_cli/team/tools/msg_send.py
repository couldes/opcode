from collections.abc import Callable

from opcode_cli.team.mailbox import Mailbox
from opcode_cli.team.registry import NameRegistry
from opcode_cli.team.types import MailboxMessage
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamMsgSendTool(BaseTool):
    """向指定成员发送点对点消息。"""

    name = "team_msg_send"
    read_only = False
    description = (
        "Send a point-to-point message to another team member. "
        "Use the 'protocol' field for structured messages: "
        "'approval_request' (send a plan for Lead approval), "
        "'approval_response' (approve/reject a plan), "
        "'task_assignment' (assign a task to a member), "
        "'status_report' (report your status to Lead)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient member name.",
            },
            "body": {
                "type": "string",
                "description": "Message body text.",
            },
            "protocol": {
                "type": "string",
                "description": "Protocol type: approval_request, approval_response, "
                "task_assignment, status_report, or empty for plain message.",
            },
            "summary": {
                "type": "string",
                "description": "Optional one-line summary.",
            },
            "extra": {
                "type": "object",
                "description": "Protocol-specific extra fields as key-value pairs.",
            },
        },
        "required": ["to", "body"],
    }

    def __init__(
        self,
        sender_name: str,
        mailbox_factory: Callable[[str], Mailbox],
        registry: NameRegistry,
        wake_callback: Callable[[str], None] | None = None,
    ):
        super().__init__()
        self._sender = sender_name
        self._mailbox_factory = mailbox_factory
        self._registry = registry
        self._wake_callback = wake_callback

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        to_name = kwargs["to"]
        recipient = self._registry.lookup(to_name)
        if recipient is None:
            return ToolResult(
                success=False, content="",
                error=f"Member not found: '{to_name}'",
            )

        msg = MailboxMessage(
            sender=self._sender,
            body=kwargs["body"],
            summary=kwargs.get("summary", ""),
            protocol=kwargs.get("protocol", ""),
            extra=kwargs.get("extra", {}),
        )

        try:
            recipient_mb = self._mailbox_factory(to_name)
            msg_id = recipient_mb.send(msg)
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Failed to send: {e}")

        # 同时发一份到自己的邮箱（留底）
        try:
            self_mb = self._mailbox_factory(self._sender)
            msg.is_read = True
            self_mb.send(msg)
        except Exception:
            pass

        # 唤醒目标成员（独立进程后端需要）
        if self._wake_callback:
            self._wake_callback(to_name)

        return ToolResult(success=True, content=f"Message sent to '{to_name}' (id: {msg_id})")
