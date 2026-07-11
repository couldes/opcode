from opcode_cli.commands import Command, CommandRegistry, get_completions


def _make_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register(Command(
        name="help", aliases=["?"], description="help",
        usage="/help", cmd_type="local", handler=lambda _: "", hidden=False,
    ))
    reg.register(Command(
        name="session", aliases=["sess", "s"], description="session",
        usage="/session", cmd_type="ui", handler=lambda _, ui: None, hidden=False,
    ))
    reg.register(Command(
        name="status", aliases=["st"], description="status",
        usage="/status", cmd_type="local", handler=lambda _: "", hidden=False,
    ))
    reg.register(Command(
        name="hidden_cmd", aliases=["hx"], description="hidden",
        usage="/hidden", cmd_type="local", handler=lambda _: "", hidden=True,
    ))
    reg.register(Command(
        name="plan", aliases=[], description="plan",
        usage="/plan", cmd_type="ui", handler=lambda _, ui: None, hidden=False,
    ))
    return reg


def test_exact_prefix_match():
    reg = _make_registry()
    comps = get_completions("h", reg)
    assert "help" in comps
    assert "hidden_cmd" not in comps  # hidden


def test_multiple_matches():
    reg = _make_registry()
    comps = get_completions("s", reg)
    assert "session" in comps
    assert "status" in comps
    assert "st" in comps
    assert "sess" in comps


def test_single_match():
    reg = _make_registry()
    comps = get_completions("plan", reg)
    assert comps == ["plan"]


def test_no_match():
    reg = _make_registry()
    comps = get_completions("xyz", reg)
    assert comps == []


def test_empty_returns_all():
    reg = _make_registry()
    comps = get_completions("", reg)
    assert "help" in comps
    assert "session" in comps
    assert "status" in comps
    assert "plan" in comps
    assert "hidden_cmd" not in comps


def test_alias_matches():
    reg = _make_registry()
    comps = get_completions("st", reg)
    assert "status" in comps
    assert "st" in comps
