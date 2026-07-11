import asyncio
import tempfile

import pytest

from opcode_cli.hooks.types import (
    HookAction,
    HookCondition,
    HookContext,
    HookDefinition,
)
from opcode_cli.hooks.runner import HookRunner

_PROJECT_ROOT = tempfile.mkdtemp()


def make_ctx(**data):
    return HookContext(
        event="",
        session_id="s1",
        project_root=_PROJECT_ROOT,
        timestamp=0.0,
        data=data,
    )


def make_hook(name="h1", event="tool_post_execute", action_type="command",
              command="echo hi", condition=None, run_once=False, background=False,
              timeout=30.0, scope="once", content=None):
    if action_type == "prompt":
        action = HookAction(type="prompt", content=content or "hello")
    else:
        action = HookAction(type=action_type, command=command)
    action.scope = scope
    return HookDefinition(
        name=name, event=event, action=action,
        condition=condition, run_once=run_once,
        background=background, timeout=timeout,
    )


class TestHookRunnerFire:
    @pytest.mark.asyncio
    async def test_no_matching_hooks(self):
        runner = HookRunner([], make_ctx())
        result = await runner.fire("tool_post_execute", {"tool_name": "x"})
        assert result.results == []
        assert result.intercept is None

    @pytest.mark.asyncio
    async def test_dispatches_to_matching_event(self):
        hook = make_hook(name="test", event="tool_post_execute", command="echo hello")
        runner = HookRunner([hook], make_ctx())
        result = await runner.fire("tool_post_execute", {})
        assert len(result.results) == 1
        assert result.results[0].hook_name == "test"
        assert result.results[0].triggered is True
        assert result.results[0].executed is True
        assert result.results[0].action_type == "command"

    @pytest.mark.asyncio
    async def test_skips_non_matching_event(self):
        hook = make_hook(name="test", event="tool_post_execute", command="echo hi")
        runner = HookRunner([hook], make_ctx())
        result = await runner.fire("iteration_start", {})
        assert result.results == []

    @pytest.mark.asyncio
    async def test_event_indexed_correctly(self):
        h1 = make_hook(name="h1", event="user_input", command="echo a")
        h2 = make_hook(name="h2", event="tool_post_execute", command="echo b")
        runner = HookRunner([h1, h2], make_ctx())

        r1 = await runner.fire("user_input", {})
        assert len(r1.results) == 1
        assert r1.results[0].hook_name == "h1"

        r2 = await runner.fire("tool_post_execute", {})
        assert len(r2.results) == 1
        assert r2.results[0].hook_name == "h2"


class TestHookRunnerRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_prevents_re_execution(self):
        hook = make_hook(name="test", event="tool_post_execute", command="echo hi", run_once=True)
        runner = HookRunner([hook], make_ctx())

        r1 = await runner.fire("tool_post_execute", {})
        assert r1.results[0].executed is True

        r2 = await runner.fire("tool_post_execute", {})
        assert r2.results[0].executed is False

    @pytest.mark.asyncio
    async def test_run_once_tracks_per_name(self):
        h1 = make_hook(name="h1", event="tool_post_execute", command="echo a", run_once=True)
        h2 = make_hook(name="h2", event="tool_post_execute", command="echo b", run_once=True)
        runner = HookRunner([h1, h2], make_ctx())

        r1 = await runner.fire("tool_post_execute", {})
        assert r1.results[0].executed is True
        assert r1.results[1].executed is True

        r2 = await runner.fire("tool_post_execute", {})
        assert r2.results[0].executed is False
        assert r2.results[1].executed is False

    @pytest.mark.asyncio
    async def test_run_once_false_re_executes(self):
        hook = make_hook(name="test", event="tool_post_execute", command="echo hi", run_once=False)
        runner = HookRunner([hook], make_ctx())

        await runner.fire("tool_post_execute", {})
        r2 = await runner.fire("tool_post_execute", {})
        assert r2.results[0].executed is True


class TestHookRunnerConditions:
    @pytest.mark.asyncio
    async def test_condition_match_trigger(self):
        cond = HookCondition(mode="all", match={"tool_name": "read_file"})
        hook = make_hook(name="test", event="tool_post_execute", command="echo hi", condition=cond)
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_post_execute", {"tool_name": "read_file"})
        assert r.results[0].triggered is True
        assert r.results[0].executed is True

    @pytest.mark.asyncio
    async def test_condition_no_match_skips(self):
        cond = HookCondition(mode="all", match={"tool_name": "read_file"})
        hook = make_hook(name="test", event="tool_post_execute", command="echo hi", condition=cond)
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_post_execute", {"tool_name": "write_file"})
        assert r.results[0].triggered is False
        assert r.results[0].executed is False

    @pytest.mark.asyncio
    async def test_no_condition_always_triggers(self):
        hook = make_hook(name="test", event="tool_post_execute", command="echo hi", condition=None)
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_post_execute", {"anything": "x"})
        assert r.results[0].triggered is True


class TestHookRunnerPromptInjection:
    @pytest.mark.asyncio
    async def test_persist_prompt(self):
        hook = make_hook(name="test", event="user_input", action_type="prompt",
                         content="persist me", scope="persist")
        runner = HookRunner([hook], make_ctx())

        await runner.fire("user_input", {})
        prompts = runner.pending_prompts()
        assert "persist me" in prompts

    @pytest.mark.asyncio
    async def test_persist_prompt_repeats(self):
        hook = make_hook(name="test", event="user_input", action_type="prompt",
                         content="persist me", scope="persist")
        runner = HookRunner([hook], make_ctx())

        await runner.fire("user_input", {})
        assert runner.pending_prompts() == ["persist me"]
        # Second fire adds another
        await runner.fire("user_input", {})
        assert runner.pending_prompts() == ["persist me", "persist me"]

    @pytest.mark.asyncio
    async def test_once_prompt_consumed(self):
        hook = make_hook(name="test", event="user_input", action_type="prompt",
                         content="once me", scope="once")
        runner = HookRunner([hook], make_ctx())

        await runner.fire("user_input", {})
        prompts = runner.consume_once_prompts()
        assert "once me" in prompts
        # Second call returns empty
        assert runner.consume_once_prompts() == []

    @pytest.mark.asyncio
    async def test_tool_pre_execute_intercepts(self):
        hook = make_hook(name="test", event="tool_pre_execute", action_type="prompt",
                         content="blocked: unsafe tool")
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_pre_execute", {"tool_name": "run_command"})
        assert r.intercept == "blocked: unsafe tool"

    @pytest.mark.asyncio
    async def test_non_prompt_action_does_not_intercept(self):
        hook = make_hook(name="test", event="tool_pre_execute", command="echo hi")
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_pre_execute", {"tool_name": "run_command"})
        assert r.intercept is None

    @pytest.mark.asyncio
    async def test_multiple_prompts_mixed_scopes(self):
        h1 = make_hook(name="h1", event="user_input", action_type="prompt",
                       content="persist", scope="persist")
        h2 = make_hook(name="h2", event="user_input", action_type="prompt",
                       content="once", scope="once")
        runner = HookRunner([h1, h2], make_ctx())

        await runner.fire("user_input", {})
        assert runner.pending_prompts() == ["persist"]
        assert runner.consume_once_prompts() == ["once"]


class TestHookRunnerBackground:
    @pytest.mark.asyncio
    async def test_background_hook_returns_immediately(self):
        hook = make_hook(name="test", event="tool_post_execute", action_type="prompt",
                         content="bg prompt", background=True)
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_post_execute", {})
        assert r.results[0].executed is True
        assert r.results[0].output == "(background)"
        # Allow background task to settle
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_background_hook_no_intercept(self):
        hook = make_hook(name="test", event="tool_pre_execute", action_type="prompt",
                         content="block", background=True)
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_pre_execute", {})
        # Background hooks skip prompt injection logic
        assert r.intercept is None
        # Allow background task to settle
        await asyncio.sleep(0.05)


class TestHookRunnerClear:
    @pytest.mark.asyncio
    async def test_clear_resets_state(self):
        hook = make_hook(name="test", event="user_input", action_type="prompt",
                         content="persist me", scope="persist", run_once=True)
        runner = HookRunner([hook], make_ctx())

        await runner.fire("user_input", {})
        assert len(runner.pending_prompts()) == 1

        runner.clear()
        assert runner.pending_prompts() == []
        assert runner.consume_once_prompts() == []

        # run_once should also reset
        r = await runner.fire("user_input", {})
        assert r.results[0].executed is True


class TestHookRunnerPlaceholderResolution:
    @pytest.mark.asyncio
    async def test_resolves_placeholders_in_command(self):
        hook = make_hook(name="test", event="tool_post_execute",
                         command="echo {{tool_name}}")
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_post_execute", {"tool_name": "read_file"})
        assert r.results[0].success is True

    @pytest.mark.asyncio
    async def test_resolves_context_top_level_fields(self):
        hook = make_hook(name="test", event="tool_post_execute",
                         command="echo {{session_id}}")
        ctx = HookContext(event="", session_id="abc123", project_root=_PROJECT_ROOT,
                          timestamp=0.0, data={})
        runner = HookRunner([hook], ctx)

        r = await runner.fire("tool_post_execute", {})
        assert r.results[0].success is True


class TestHookRunnerErrorHandling:
    @pytest.mark.asyncio
    async def test_command_failure_reported(self):
        # A command that will fail
        hook = make_hook(name="test", event="tool_post_execute",
                         command="nonexistent_command_xyz")
        runner = HookRunner([hook], make_ctx())

        r = await runner.fire("tool_post_execute", {})
        assert r.results[0].success is False
        assert r.results[0].executed is True

    @pytest.mark.asyncio
    async def test_multiple_hooks_independent(self):
        """If one hook fails, other hooks still execute."""
        h1 = make_hook(name="h1", event="tool_post_execute",
                       command="nonexistent_cmd")
        h2 = make_hook(name="h2", event="tool_post_execute", command="echo ok")
        runner = HookRunner([h1, h2], make_ctx())

        r = await runner.fire("tool_post_execute", {})
        assert len(r.results) == 2
        assert r.results[0].success is False
        assert r.results[1].success is True
