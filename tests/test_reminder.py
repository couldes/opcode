from opcode_cli.prompt.reminder import system_reminder


def test_system_reminder_role_is_user():
    msg = system_reminder("test content")
    assert msg.role == "user"


def test_system_reminder_wraps_with_tags():
    msg = system_reminder("test content")
    assert msg.content.startswith("<system-reminder>\n")
    assert msg.content.endswith("\n</system-reminder>")


def test_system_reminder_preserves_content():
    msg = system_reminder("test content")
    assert "test content" in msg.content


def test_system_reminder_content_between_tags():
    msg = system_reminder("hello world")
    inner = msg.content.replace("<system-reminder>\n", "").replace("\n</system-reminder>", "")
    assert inner == "hello world"


def test_system_reminder_empty_content():
    msg = system_reminder("")
    assert "<system-reminder>" in msg.content
    assert "</system-reminder>" in msg.content
