import pytest
from opcode_cli.permission.rules import Rule, RuleSet, parse_rule_spec


class TestParseRuleSpec:
    def test_allow_rule(self):
        rule = parse_rule_spec("Bash(git *)", "allow")
        assert rule.tool_name == "run_command"
        assert rule.pattern == "git *"
        assert rule.action == "allow"

    def test_deny_rule(self):
        rule = parse_rule_spec("Write(*.env)", "deny")
        assert rule.tool_name == "write_file"
        assert rule.pattern == "*.env"
        assert rule.action == "deny"

    def test_alias_resolution(self):
        assert parse_rule_spec("Read(*.py)", "allow").tool_name == "read_file"
        assert parse_rule_spec("Edit(*)", "deny").tool_name == "edit_file"
        assert parse_rule_spec("Glob(**/*)", "allow").tool_name == "glob_find"
        assert parse_rule_spec("Grep(*)", "allow").tool_name == "grep_search"

    def test_invalid_action(self):
        with pytest.raises(ValueError):
            parse_rule_spec("Bash(*)", "maybe")

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_rule_spec("Bash", "allow")


class TestRuleSet:
    def test_exact_match(self):
        rs = RuleSet()
        rs.add(Rule("run_command", "git status", "allow"))
        assert rs.match("run_command", "git status") == "allow"

    def test_glob_match(self):
        rs = RuleSet()
        rs.add(Rule("run_command", "git *", "allow"))
        assert rs.match("run_command", "git push") == "allow"
        assert rs.match("run_command", "git status") == "allow"

    def test_no_match(self):
        rs = RuleSet()
        rs.add(Rule("run_command", "git *", "allow"))
        assert rs.match("run_command", "npm run") is None

    def test_no_match_different_tool(self):
        rs = RuleSet()
        rs.add(Rule("run_command", "git *", "allow"))
        assert rs.match("write_file", "git push") is None

    def test_first_match_wins(self):
        rs = RuleSet()
        rs.add(Rule("run_command", "git push", "deny"))
        rs.add(Rule("run_command", "git *", "allow"))
        assert rs.match("run_command", "git push") == "deny"

    def test_empty_ruleset(self):
        rs = RuleSet()
        assert rs.match("run_command", "anything") is None

    def test_session_rules_override(self):
        base = RuleSet()
        base.add(Rule("run_command", "git *", "allow"))

        session = RuleSet()
        session.add(Rule("run_command", "git push", "deny"))

        # session check first
        assert session.match("run_command", "git push") == "deny"
        # base falls back
        assert base.match("run_command", "git push") == "allow"
