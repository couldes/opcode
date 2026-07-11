from opcode_cli.team.mailbox import Mailbox
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamMsgReadTool(BaseTool):
    """读取自己的收件箱。"""

    name = "team_msg_read"
    read_only = True
    description = (
        "Read messages from your team mailbox. "
        "Supports filtering by sender and unread status. "
        "Use mark_read=true to mark matching messages as read."
    )
    parameters = {
        "type": "object",
        "properties": {
            "unread_only": {
                "type": "boolean",
                "description": "Only show unread messages. Default: false.",
            },
            "sender": {
                "type": "string",
                "description": "Filter by sender name.",
            },
            "mark_read": {
                "type": "boolean",
                "description": "Mark matching messages as read. Default: false.",
            },
        },
        "required": [],
    }

    def __init__(self, mailbox: Mailbox):
        super().__init__()
        self._mailbox = mailbox

    async def execute(self, working_dir: str | None = None, **kwargs) -> ToolResult:
        msgs = self._mailbox.read_all(
            unread_only=kwargs.get("unread_only", False),
            sender=kwargs.get("sender"),
        )
        if not msgs:
            return ToolResult(success=True, content="No messages.")

        if kwargs.get("mark_read"):
            for m in msgs:
                if not m.is_read:
                    self._mailbox.mark_read(m.msg_id)

        lines = []
        for m in msgs:
            proto = f" [{m.protocol}]" if m.protocol else ""
            status = " " if m.is_read else "*"
            extra_str = f" extra={m.extra}" if m.extra else ""
            lines.append(f"[{m.msg_id}]{status}{m.sender}@{m.timestamp}: {m.body}{proto}{extra_str}")
        return ToolResult(success=True, content="\n".join(lines))
