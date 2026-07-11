from opcode_cli.hooks.matcher import _match_pattern, _resolve_field, match_condition
from opcode_cli.hooks.types import HookCondition


class TestMatchPattern:
    def test_exact(self):
        assert _match_pattern("run_command", "run_command") is True
        assert _match_pattern("run_command", "read_file") is False
        assert _match_pattern("", "") is True

    def test_inverse(self):
        assert _match_pattern("git status", "!git push") is True
        assert _match_pattern("git push", "!git push") is False
        assert _match_pattern("git commit", "!git *") is False

    def test_regex(self):
        assert _match_pattern("hello world", "/hello/") is True
        assert _match_pattern("abc123", "/^\\d+$/") is False
        assert _match_pattern("12345", "/^\\d+$/") is True
        assert _match_pattern("rm -rf /tmp", "/rm\\s+-rf/") is True

    def test_glob(self):
        assert _match_pattern("main.py", "*.py") is True
        assert _match_pattern("main.go", "*.py") is False
        assert _match_pattern("src/main.py", "src/**") is True


class TestResolveField:
    def test_top_level(self):
        assert _resolve_field({"a": "1"}, "a") == "1"

    def test_nested(self):
        data = {"tool_args": {"path": "/tmp/x.py"}}
        assert _resolve_field(data, "tool_args.path") == "/tmp/x.py"

    def test_missing(self):
        assert _resolve_field({"a": 1}, "a.b") == ""

    def test_non_string_value(self):
        assert _resolve_field({"count": 42}, "count") == "42"


class TestMatchCondition:
    def test_none(self):
        assert match_condition(None, {}) is True
        assert match_condition(None, {"a": "1"}) is True

    def test_empty_match(self):
        c = HookCondition(mode="all", match={})
        assert match_condition(c, {"x": "y"}) is True

    def test_all_mode_both_match(self):
        c = HookCondition(mode="all", match={"a": "1", "b": "2"})
        assert match_condition(c, {"a": "1", "b": "2"}) is True

    def test_all_mode_partial(self):
        c = HookCondition(mode="all", match={"a": "1", "b": "2"})
        assert match_condition(c, {"a": "1", "b": "3"}) is False

    def test_any_mode_one_match(self):
        c = HookCondition(mode="any", match={"a": "1", "b": "2"})
        assert match_condition(c, {"a": "1", "b": "3"}) is True

    def test_any_mode_none_match(self):
        c = HookCondition(mode="any", match={"a": "1", "b": "2"})
        assert match_condition(c, {"a": "3", "b": "4"}) is False

    def test_glob_in_condition(self):
        c = HookCondition(mode="all", match={"tool_name": "*.py"})
        assert match_condition(c, {"tool_name": "main.py"}) is True
        assert match_condition(c, {"tool_name": "main.go"}) is False
