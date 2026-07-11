import pytest
from opcode_cli.permission.checker import PermissionChecker
from opcode_cli.permission.mode import PermissionMode
from opcode_cli.permission.rules import Rule, RuleSet
from opcode_cli.provider.base import ToolCall


def _tc(name, **kwargs):
    return ToolCall(id="id1", name=name, input=kwargs)


class TestPermissionChecker:
    def test_l1_blacklist_blocks_dangerous_command(self):
        checker = PermissionChecker("/project", PermissionMode.PERMISSIVE)
        result = checker.check(_tc("run_command", command="rm -rf /"))
        assert result == "deny"

    def test_l1_blacklist_allows_safe_command(self):
        checker = PermissionChecker("/project", PermissionMode.DEFAULT)
        result = checker.check(_tc("run_command", command="echo hello"))
        assert result == "ask_user"  # falls through to L4 default

    def test_l2_sandbox_blocks_outside_path(self):
        checker = PermissionChecker("/project", PermissionMode.PERMISSIVE)
        result = checker.check(_tc("read_file", path="/etc/passwd"))
        assert result == "deny"

    def test_l2_sandbox_allows_inside_path(self, tmp_path):
        checker = PermissionChecker(str(tmp_path), PermissionMode.DEFAULT)
        f = tmp_path / "test.txt"
        f.write_text("hi")
        result = checker.check(_tc("read_file", path=str(f)))
        assert result == "allow"  # L4: DEFAULT + read_only=True → allow

    def test_l3_rule_allow(self):
        rules = RuleSet()
        rules.add(Rule("run_command", "git *", "allow"))
        checker = PermissionChecker("/project", PermissionMode.STRICT, base_rules=rules)
        result = checker.check(_tc("run_command", command="git status"))
        assert result == "allow"

    def test_l3_rule_deny(self):
        rules = RuleSet()
        rules.add(Rule("run_command", "npm publish", "deny"))
        checker = PermissionChecker("/project", PermissionMode.PERMISSIVE, base_rules=rules)
        result = checker.check(_tc("run_command", command="npm publish"))
        assert result == "deny"

    def test_l3_session_rule_overrides_base(self):
        base = RuleSet()
        base.add(Rule("run_command", "git *", "allow"))
        session = RuleSet()
        session.add(Rule("run_command", "git push", "deny"))
        checker = PermissionChecker("/project", PermissionMode.DEFAULT, base_rules=base, session_rules=session)
        result = checker.check(_tc("run_command", command="git push"))
        assert result == "deny"

    def test_l4_strict_denies_side_effect(self):
        checker = PermissionChecker("/project", PermissionMode.STRICT)
        result = checker.check(_tc("run_command", command="echo hello"))
        assert result == "deny"

    def test_l4_permissive_allows(self):
        checker = PermissionChecker("/project", PermissionMode.PERMISSIVE)
        result = checker.check(_tc("run_command", command="echo hello"))
        assert result == "allow"

    def test_l4_default_ask_user_for_side_effect(self):
        checker = PermissionChecker("/project", PermissionMode.DEFAULT)
        result = checker.check(_tc("run_command", command="echo hello"))
        assert result == "ask_user"

    def test_l4_default_allow_for_read_only(self):
        checker = PermissionChecker("/project", PermissionMode.DEFAULT)
        result = checker.check(_tc("read_file", path="/project/file.txt"))
        assert result == "allow"

    def test_l1_takes_priority_over_l3(self):
        rules = RuleSet()
        rules.add(Rule("run_command", "rm *", "allow"))
        checker = PermissionChecker("/project", PermissionMode.PERMISSIVE, base_rules=rules)
        result = checker.check(_tc("run_command", command="rm -rf /"))
        assert result == "deny"  # L1 blocks even though L3 allows

    def test_l2_takes_priority_over_l3(self):
        rules = RuleSet()
        rules.add(Rule("read_file", "/etc/*", "allow"))
        checker = PermissionChecker("/project", PermissionMode.PERMISSIVE, base_rules=rules)
        result = checker.check(_tc("read_file", path="/etc/passwd"))
        assert result == "deny"  # L2 blocks even though L3 allows

    def test_none_checker_skips(self):
        checker = PermissionChecker("/project", PermissionMode.PERMISSIVE)
        result = checker.check(_tc("glob_find", path="/project/src"))
        assert result == "allow"

    def test_add_session_rule(self):
        checker = PermissionChecker("/project", PermissionMode.STRICT)
        result = checker.check(_tc("run_command", command="git status"))
        assert result == "deny"  # strict mode denies
        checker.add_session_rule(Rule("run_command", "git *", "allow"))
        result = checker.check(_tc("run_command", command="git status"))
        assert result == "allow"  # session rule overrides
