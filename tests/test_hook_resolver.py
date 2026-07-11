from opcode_cli.hooks.resolver import resolve_placeholders, resolve_dict
from opcode_cli.hooks.types import HookContext


def make_ctx(**data):
    return HookContext(
        event="tool_post_execute",
        session_id="s1",
        project_root="/tmp/project",
        timestamp=1234567890.0,
        data=data,
    )


class TestResolvePlaceholders:
    def test_simple(self):
        ctx = make_ctx(tool_name="read_file")
        assert resolve_placeholders("echo {{tool_name}}", ctx) == "echo read_file"

    def test_nested(self):
        ctx = make_ctx(tool_args={"path": "/tmp/x.py"})
        assert resolve_placeholders("{{tool_args.path}}", ctx) == "/tmp/x.py"

    def test_context_top_level(self):
        ctx = make_ctx()
        assert resolve_placeholders("sid={{session_id}}", ctx) == "sid=s1"
        assert resolve_placeholders("event={{event}}", ctx) == "event=tool_post_execute"
        assert resolve_placeholders("root={{project_root}}", ctx) == "root=/tmp/project"
        assert resolve_placeholders("ts={{timestamp}}", ctx) == "ts=1234567890.0"

    def test_missing(self):
        ctx = make_ctx()
        assert resolve_placeholders("{{unknown}}", ctx) == "{{unknown}}"

    def test_multiple(self):
        ctx = make_ctx(tool_name="write_file", tool_args={"path": "out.txt"})
        result = resolve_placeholders("{{tool_name}} -> {{tool_args.path}}", ctx)
        assert result == "write_file -> out.txt"

    def test_none_template(self):
        ctx = make_ctx()
        assert resolve_placeholders(None, ctx) is None


class TestResolveDict:
    def test_shallow(self):
        ctx = make_ctx(tool_name="grep_search")
        result = resolve_dict({"cmd": "echo {{tool_name}}"}, ctx)
        assert result == {"cmd": "echo grep_search"}

    def test_nested_dict(self):
        ctx = make_ctx(tool_name="test")
        result = resolve_dict({"outer": {"inner": "{{tool_name}}"}}, ctx)
        assert result == {"outer": {"inner": "test"}}
