from opcode_cli.commands import Command, CommandRegistry, parse


def _make_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register(Command(
        name="help", aliases=["?", "h"], description="help",
        usage="/help", cmd_type="local", handler=lambda _: "",
    ))
    reg.register(Command(
        name="session", aliases=["sess"], description="session",
        usage="/session [id]", cmd_type="ui", handler=lambda _, ui: None,
    ))
    reg.register(Command(
        name="plan", aliases=[], description="plan",
        usage="/plan", cmd_type="ui", handler=lambda _, ui: None,
    ))
    return reg


def test_non_slash_input():
    reg = _make_registry()
    assert parse("hello", reg) is None
    assert parse("", reg) is None
    assert parse("  ", reg) is None


def test_slash_only():
    reg = _make_registry()
    assert parse("/", reg) is None


def test_exact_match():
    reg = _make_registry()
    p = parse("/help", reg)
    assert p is not None
    assert p.command.name == "help"
    assert p.args == ""


def test_alias_match():
    reg = _make_registry()
    p = parse("/?", reg)
    assert p is not None
    assert p.command.name == "help"
    p = parse("/sess", reg)
    assert p is not None
    assert p.command.name == "session"


def test_case_insensitive():
    reg = _make_registry()
    assert parse("/Help", reg) is not None
    assert parse("/HELP", reg) is not None
    assert parse("/Sess", reg) is not None


def test_with_args():
    reg = _make_registry()
    p = parse("/session abc123", reg)
    assert p is not None
    assert p.command.name == "session"
    assert p.args == "abc123"

    p = parse("/session abc 123", reg)
    assert p is not None
    assert p.args == "abc 123"


def test_unknown_command():
    reg = _make_registry()
    p = parse("/unknown", reg)
    assert p is None
