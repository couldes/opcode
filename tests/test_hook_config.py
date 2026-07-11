import tempfile
from pathlib import Path

import yaml

from opcode_cli.hooks.config import KNOWN_EVENTS, load_hooks, validate_hook


class TestValidateHook:
    def test_valid_command(self):
        raw = {
            "name": "test",
            "event": "tool_post_execute",
            "action": {"type": "command", "command": "echo hi"},
        }
        assert validate_hook(raw) == []

    def test_valid_prompt(self):
        raw = {
            "name": "test",
            "event": "session_start",
            "action": {"type": "prompt", "content": "hello"},
        }
        assert validate_hook(raw) == []

    def test_missing_name(self):
        assert len(validate_hook({"event": "x", "action": {"type": "command", "command": "x"}})) > 0

    def test_missing_event(self):
        assert len(validate_hook({"name": "x", "action": {"type": "command", "command": "x"}})) > 0

    def test_unknown_event(self):
        raw = {
            "name": "x",
            "event": "nonexistent_event",
            "action": {"type": "command", "command": "x"},
        }
        errors = validate_hook(raw)
        assert len(errors) > 0
        assert any("unknown event" in e.lower() for e in errors)

    def test_missing_action(self):
        assert len(validate_hook({"name": "x", "event": "tool_post_execute"})) > 0

    def test_bad_action_type(self):
        raw = {
            "name": "x",
            "event": "tool_post_execute",
            "action": {"type": "invalid"},
        }
        errors = validate_hook(raw)
        assert len(errors) > 0

    def test_tool_pre_execute_async_conflict(self):
        raw = {
            "name": "x",
            "event": "tool_pre_execute",
            "background": True,
            "action": {"type": "command", "command": "x"},
        }
        errors = validate_hook(raw)
        assert len(errors) > 0
        assert any("background" in e.lower() for e in errors)

    def test_command_missing_command_field(self):
        raw = {
            "name": "x",
            "event": "tool_post_execute",
            "action": {"type": "command"},
        }
        errors = validate_hook(raw)
        assert len(errors) > 0
        assert any("command" in e.lower() for e in errors)

    def test_prompt_missing_content_field(self):
        raw = {
            "name": "x",
            "event": "tool_post_execute",
            "action": {"type": "prompt"},
        }
        errors = validate_hook(raw)
        assert len(errors) > 0

    def test_http_missing_url_field(self):
        raw = {
            "name": "x",
            "event": "tool_post_execute",
            "action": {"type": "http"},
        }
        errors = validate_hook(raw)
        assert len(errors) > 0

    def test_bad_if_mode(self):
        raw = {
            "name": "x",
            "event": "tool_post_execute",
            "action": {"type": "command", "command": "x"},
            "if": {"mode": "invalid"},
        }
        errors = validate_hook(raw)
        assert len(errors) > 0


class TestLoadHooks:
    def test_no_config(self):
        hooks = load_hooks("/tmp/nonexistent_project_hooks_test")
        assert hooks == []

    def test_valid_yaml(self):
        d = tempfile.mkdtemp()
        p = Path(d) / ".opcode" / "hooks.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        yaml_data = {
            "hooks": [
                {
                    "name": "test-hook",
                    "event": "tool_post_execute",
                    "action": {"type": "command", "command": "echo hi"},
                }
            ]
        }
        p.write_text(yaml.dump(yaml_data))
        hooks = load_hooks(str(d))
        assert len(hooks) == 1
        assert hooks[0].name == "test-hook"
        assert hooks[0].event == "tool_post_execute"

    def test_skip_invalid_hook(self):
        d = tempfile.mkdtemp()
        p = Path(d) / ".opcode" / "hooks.yaml"
        p.parent.mkdir(parents=True, exist_ok=True)
        yaml_data = {
            "hooks": [
                {"name": "bad", "event": "bad_event", "action": {"type": "command", "command": "x"}},
                {"name": "good", "event": "tool_post_execute", "action": {"type": "command", "command": "echo good"}},
            ]
        }
        p.write_text(yaml.dump(yaml_data))
        hooks = load_hooks(str(d))
        assert len(hooks) == 1
        assert hooks[0].name == "good"

    def test_project_overrides_user(self):
        d = tempfile.mkdtemp()
        user_p = Path.home() / ".opcode" / "hooks.yaml"
        proj_p = Path(d) / ".opcode" / "hooks.yaml"
        proj_p.parent.mkdir(parents=True, exist_ok=True)
        user_p.parent.mkdir(parents=True, exist_ok=True)

        user_yaml = {"hooks": [{"name": "myhook", "event": "tool_post_execute",
            "action": {"type": "command", "command": "user"}}]}
        proj_yaml = {"hooks": [{"name": "myhook", "event": "tool_post_execute",
            "action": {"type": "command", "command": "project"}}]}

        # Write user hook
        user_p.write_text(yaml.dump(user_yaml))
        proj_p.write_text(yaml.dump(proj_yaml))

        try:
            hooks = load_hooks(str(d))
            assert len(hooks) == 1
            assert hooks[0].action.command == "project"
        finally:
            # Cleanup
            user_p.unlink(missing_ok=True)
