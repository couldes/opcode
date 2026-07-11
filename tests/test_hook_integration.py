import tempfile

import pytest

from opcode_cli.hooks.types import (
    HookAction,
    HookCondition,
    HookContext,
    HookDefinition,
)
from opcode_cli.hooks.runner import HookRunner
from opcode_cli.hooks.config import validate_hook, _raw_to_hook

_PROJECT_ROOT = tempfile.mkdtemp()


class TestEndToEndLifecycle:
    """Simulates a full agent lifecycle with hooks at multiple events."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        hooks = [
            HookDefinition(
                name="session-start-log",
                event="session_start",
                action=HookAction(type="command", command="echo session_started"),
            ),
            HookDefinition(
                name="user-input-log",
                event="user_input",
                action=HookAction(type="command", command="echo user_input_received"),
            ),
            HookDefinition(
                name="tool-post-log",
                event="tool_post_execute",
                action=HookAction(type="command", command="echo tool_done"),
            ),
            HookDefinition(
                name="iteration-end-log",
                event="iteration_end",
                action=HookAction(type="command", command="echo iteration_done"),
            ),
        ]
        base_ctx = HookContext(
            event="", session_id="s1", project_root=_PROJECT_ROOT, timestamp=0.0, data={},
        )
        runner = HookRunner(hooks, base_ctx)

        # Simulate lifecycle
        r1 = await runner.fire("session_start", {"provider_type": "Anthropic"})
        assert len(r1.results) == 1
        assert r1.results[0].success is True

        r2 = await runner.fire("user_input", {"input_text": "hello"})
        assert len(r2.results) == 1
        assert r2.results[0].success is True

        r3 = await runner.fire("tool_post_execute", {"tool_name": "read_file"})
        assert len(r3.results) == 1
        assert r3.results[0].success is True

        r4 = await runner.fire("iteration_end", {"iteration": 1})
        assert len(r4.results) == 1
        assert r4.results[0].success is True

    @pytest.mark.asyncio
    async def test_tool_pre_execute_intercept_flow(self):
        """tool_pre_execute hook intercepts, then tool is not executed."""
        hooks = [
            HookDefinition(
                name="block-dangerous",
                event="tool_pre_execute",
                action=HookAction(type="prompt", content="blocked: dangerous command"),
                condition=HookCondition(mode="all", match={"tool_name": "run_command"}),
            ),
        ]
        base_ctx = HookContext(
            event="", session_id="s1", project_root=_PROJECT_ROOT, timestamp=0.0, data={},
        )
        runner = HookRunner(hooks, base_ctx)

        # Should intercept
        r1 = await runner.fire("tool_pre_execute", {
            "tool_name": "run_command",
            "tool_args": {"command": "rm -rf /"},
        })
        assert r1.intercept == "blocked: dangerous command"

        # Should NOT intercept (different tool)
        r2 = await runner.fire("tool_pre_execute", {
            "tool_name": "read_file",
            "tool_args": {"path": "/tmp/test.txt"},
        })
        assert r2.intercept is None

    @pytest.mark.asyncio
    async def test_prompt_injection_flow(self):
        """Prompt hooks inject content via persist and once scopes."""
        hooks = [
            HookDefinition(
                name="inject-context",
                event="user_input",
                action=HookAction(type="prompt", content="Remember: use Python 3.12",
                                  scope="persist"),
            ),
            HookDefinition(
                name="inject-temp",
                event="session_start",
                action=HookAction(type="prompt", content="Welcome to the session!",
                                  scope="once"),
            ),
        ]
        base_ctx = HookContext(
            event="", session_id="s1", project_root=_PROJECT_ROOT, timestamp=0.0, data={},
        )
        runner = HookRunner(hooks, base_ctx)

        # Fire session_start -> once prompt
        await runner.fire("session_start", {})
        assert runner.consume_once_prompts() == ["Welcome to the session!"]
        # After consume, it should be empty
        assert runner.consume_once_prompts() == []

        # Fire user_input -> persist prompt
        await runner.fire("user_input", {"input_text": "hello"})
        assert "Remember: use Python 3.12" in runner.pending_prompts()
        # Persist prompts survive across multiple fires
        await runner.fire("user_input", {"input_text": "world"})
        assert len(runner.pending_prompts()) == 2

    @pytest.mark.asyncio
    async def test_run_once_combined_with_condition(self):
        """run_once + condition: hook only fires once even if condition matches later."""
        hooks = [
            HookDefinition(
                name="alert-on-error",
                event="error",
                action=HookAction(type="command", command="echo alert"),
                condition=HookCondition(mode="all", match={"error_type": "ValueError"}),
                run_once=True,
            ),
        ]
        base_ctx = HookContext(
            event="", session_id="s1", project_root=_PROJECT_ROOT, timestamp=0.0, data={},
        )
        runner = HookRunner(hooks, base_ctx)

        r1 = await runner.fire("error", {"error_type": "ValueError", "error_message": "bad"})
        assert r1.results[0].executed is True

        r2 = await runner.fire("error", {"error_type": "ValueError", "error_message": "bad again"})
        assert r2.results[0].executed is False


class TestConfigToRunnerIntegration:
    """Tests the flow from YAML config to HookDefinition to HookRunner."""

    def test_valid_config_produces_runnable_hooks(self):
        raw = {
            "name": "log-tool",
            "event": "tool_post_execute",
            "action": {"type": "command", "command": "echo {{tool_name}}"},
            "if": {"mode": "all", "match": {"tool_name": "*.py"}},
            "run_once": False,
            "timeout": 10.0,
        }
        errors = validate_hook(raw)
        assert errors == []

        hook = _raw_to_hook(raw)
        assert hook.name == "log-tool"
        assert hook.event == "tool_post_execute"
        assert hook.action.type == "command"
        assert hook.action.command == "echo {{tool_name}}"
        assert hook.condition is not None
        assert hook.condition.mode == "all"
        assert hook.timeout == 10.0

    def test_config_with_prompt_action(self):
        raw = {
            "name": "inject",
            "event": "user_input",
            "action": {"type": "prompt", "content": "System note: use strict typing",
                       "scope": "persist"},
        }
        errors = validate_hook(raw)
        assert errors == []

        hook = _raw_to_hook(raw)
        assert hook.action.type == "prompt"
        assert hook.action.scope == "persist"

    def test_config_with_http_action(self):
        raw = {
            "name": "webhook",
            "event": "tool_post_execute",
            "action": {
                "type": "http",
                "url": "https://example.com/webhook",
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": "{\"tool\": \"{{tool_name}}\"}",
            },
        }
        errors = validate_hook(raw)
        assert errors == []

        hook = _raw_to_hook(raw)
        assert hook.action.type == "http"
        assert hook.action.url == "https://example.com/webhook"
        assert hook.action.method == "POST"

    def test_multiple_mixed_hooks_config(self):
        raws = [
            {
                "name": "h1",
                "event": "session_start",
                "action": {"type": "command", "command": "echo start"},
            },
            {
                "name": "h2",
                "event": "tool_post_execute",
                "action": {"type": "prompt", "content": "done"},
                "if": {"mode": "any", "match": {"tool_name": "read_file",
                                                 "success": "True"}},
            },
        ]
        hooks = []
        for raw in raws:
            assert validate_hook(raw) == []
            hooks.append(_raw_to_hook(raw))

        assert len(hooks) == 2
        assert hooks[0].event == "session_start"
        assert hooks[1].condition.mode == "any"
        assert len(hooks[1].condition.match) == 2
