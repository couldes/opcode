from collections.abc import Callable

from opcode_cli.team.mailbox import Mailbox
from opcode_cli.team.registry import NameRegistry
from opcode_cli.team.types import MailboxMessage
from opcode_cli.tools.base import BaseTool, ToolResult


class TeamMsgBroadcastTool(BaseTool):
    """向全体成员广播消息。"""

    name = "team_msg_broadcast"
    read_only = False
    description = "Broadcast a message to all team members."
    parameters = {
        "type": "object",
        "properties": {
            "body": {
                "type": "string",
                "description": "Message body text.",
            },
            "summary": {
                "type": "string",
                "description": "Optional one-line summary.",
            },
        },
        "required": ["body"],
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
        online = self._registry.list_online()
        sent = []
        failed = []

        for name in online:
            if name == self._sender:
                continue
            msg = MailboxMessage(
                sender=self._sender,
                body=kwargs["body"],
                summary=kwargs.get("summary", ""),
            )
            try:
                mb = self._mailbox_factory(name)
                mb.send(msg)
                sent.append(name)
                if self._wake_callback:
                    self._wake_callback(name)
            except Exception:
                failed.append(name)

        result = f"Broadcast to {len(sent)} members."
        if failed:
            result += f" Failed: {', '.join(failed)}."
        return ToolResult(success=True, content=result)
