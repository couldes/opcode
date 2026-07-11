import os
import tempfile
from pathlib import Path

from opcode_cli.permission.config import load_rule_file, merge_rulesets, resolve_rule_paths
from opcode_cli.permission.rules import RuleSet


class TestLoadRuleFile:

    def test_load_valid_yaml(self):
        content = """rules:
  - allow: "Bash(git *)"
  - deny: "Write(*.env)"
  - allow: "Read(**/*.py)"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            rs = load_rule_file(Path(path))
            assert rs is not None
            assert rs.match("run_command", "git status") == "allow"
            assert rs.match("write_file", ".env") == "deny"
            assert rs.match("read_file", "src/main.py") == "allow"
        finally:
            os.unlink(path)

    def test_load_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            path = f.name
        try:
            rs = load_rule_file(Path(path))
            assert rs is None
        finally:
            os.unlink(path)

    def test_load_file_not_found(self):
        rs = load_rule_file(Path("/nonexistent/rules.yaml"))
        assert rs is None

    def test_load_invalid_yaml(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("rules: [invalid: [")
            path = f.name
        try:
            rs = load_rule_file(Path(path))
            assert rs is None  # should not raise, just return None
        finally:
            os.unlink(path)

    def test_load_skips_invalid_rule(self):
        content = """rules:
  - allow: "Bash(git *)"
  - invalid_format
  - deny: "Write(*.env)"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            rs = load_rule_file(Path(path))
            assert rs is not None
            # valid rules still loaded
            assert rs.match("run_command", "git status") == "allow"
            assert rs.match("write_file", ".env") == "deny"
        finally:
            os.unlink(path)

    def test_load_no_rules_key(self):
        content = "other: value"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            path = f.name
        try:
            rs = load_rule_file(Path(path))
            assert rs is None
        finally:
            os.unlink(path)


class TestMergeRuleSets:

    def test_merge_with_priority(self):
        user = RuleSet()
        from opcode_cli.permission.rules import Rule
        user.add(Rule("run_command", "git *", "deny"))
        project = RuleSet()
        project.add(Rule("run_command", "git *", "allow"))
        merged = merge_rulesets(project, user)
        # project rules checked first (higher priority)
        assert merged.match("run_command", "git status") == "allow"

    def test_merge_empty_layers(self):
        merged = merge_rulesets()
        assert merged.match("run_command", "anything") is None

    def test_merge_single_layer(self):
        from opcode_cli.permission.rules import Rule
        rs = RuleSet()
        rs.add(Rule("run_command", "echo *", "allow"))
        merged = merge_rulesets(rs)
        assert merged.match("run_command", "echo hello") == "allow"


class TestResolveRulePaths:

    def test_returns_paths(self):
        project, user = resolve_rule_paths("/home/user/project")
        assert "opcode" in str(project) and "rules.yaml" in str(project)
        assert "opcode" in str(user) and "rules.yaml" in str(user)
