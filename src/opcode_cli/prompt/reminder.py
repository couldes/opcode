from opcode_cli.provider.base import Message


def system_reminder(content: str) -> Message:
    return Message(
        role="user",
        content=f"<system-reminder>\n{content}\n</system-reminder>",
    )
