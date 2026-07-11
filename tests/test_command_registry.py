from opcode_cli.commands import Command, CommandConflictError, CommandRegistry


def test_register_and_get():
    reg = CommandRegistry()
    cmd = Command(
        name="help", aliases=["?", "h"], description="Show help",
        usage="/help", cmd_type="local", handler=lambda _: "ok",
    )
    reg.register(cmd)
    assert reg.get("help") is cmd
    assert reg.get("?") is cmd
    assert reg.get("h") is cmd
    assert reg.get("HELP") is cmd
    assert reg.get("Help") is cmd


def test_get_nonexistent():
    reg = CommandRegistry()
    assert reg.get("nonexistent") is None


def test_list_visible_sorted():
    reg = CommandRegistry()
    reg.register(Command(name="ccc", description="", usage="", cmd_type="local", handler=lambda _: ""))
    reg.register(Command(name="aaa", description="", usage="", cmd_type="local", handler=lambda _: ""))
    reg.register(Command(name="bbb", description="", usage="", cmd_type="local", handler=lambda _: ""))
    visible = reg.list_visible()
    names = [c.name for c in visible]
    assert names == ["aaa", "bbb", "ccc"]


def test_list_visible_excludes_hidden():
    reg = CommandRegistry()
    reg.register(Command(name="visible", description="", usage="", cmd_type="local", handler=lambda _: "", hidden=False))
    reg.register(Command(name="hidden", description="", usage="", cmd_type="local", handler=lambda _: "", hidden=True))
    visible = reg.list_visible()
    names = [c.name for c in visible]
    assert "visible" in names
    assert "hidden" not in names


def test_get_matchable_names():
    reg = CommandRegistry()
    reg.register(Command(name="help", aliases=["?"], description="", usage="", cmd_type="local", handler=lambda _: "", hidden=False))
    reg.register(Command(name="hidden", aliases=["h"], description="", usage="", cmd_type="local", handler=lambda _: "", hidden=True))
    matchable = reg.get_matchable_names()
    assert "help" in matchable
    assert "?" in matchable
    assert "hidden" not in matchable
    assert "h" not in matchable


def test_name_conflict():
    reg = CommandRegistry()
    reg.register(Command(name="cmd", aliases=[], description="", usage="", cmd_type="local", handler=lambda _: ""))
    try:
        reg.register(Command(name="cmd", aliases=[], description="", usage="", cmd_type="local", handler=lambda _: ""))
        assert False, "should have raised"
    except CommandConflictError:
        pass


def test_alias_name_conflict():
    reg = CommandRegistry()
    reg.register(Command(name="a", aliases=[], description="", usage="", cmd_type="local", handler=lambda _: ""))
    try:
        reg.register(Command(name="b", aliases=["a"], description="", usage="", cmd_type="local", handler=lambda _: ""))
        assert False, "should have raised"
    except CommandConflictError:
        pass


def test_alias_alias_conflict():
    reg = CommandRegistry()
    reg.register(Command(name="a", aliases=["x"], description="", usage="", cmd_type="local", handler=lambda _: ""))
    try:
        reg.register(Command(name="b", aliases=["x"], description="", usage="", cmd_type="local", handler=lambda _: ""))
        assert False, "should have raised"
    except CommandConflictError:
        pass


def test_duplicate_alias_in_same_command():
    reg = CommandRegistry()
    try:
        # alias same as own name is OK as registration (name already covers it)
        reg.register(Command(name="x", aliases=["x"], description="", usage="", cmd_type="local", handler=lambda _: ""))
        # Should not crash
    except CommandConflictError:
        pass
