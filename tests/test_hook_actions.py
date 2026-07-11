import os
import tempfile

import pytest

from opcode_cli.hooks.types import HookAction, HookContext, HookDefinition
from opcode_cli.hooks.actions.command import run_command
from opcode_cli.hooks.actions.prompt import run_prompt
from opcode_cli.hooks.actions.http_action import run_http
from opcode_cli.hooks.actions.agent import run_agent
from opcode_cli.hooks.actions import dispatch

_PROJECT_ROOT = tempfile.mkdtemp()


def make_ctx(event="tool_post_execute", **data):
    return HookContext(
        event=event,
        session_id="s1",
        project_root=_PROJECT_ROOT,
        timestamp=1234567890.0,
        data=data,
    )


def make_hook(name="test", event="tool_post_execute", action_type="command",
              command=None, content=None, url=None, timeout=30.0, method="POST",
              headers=None, body=None, **kwargs):
    action = HookAction(
        type=action_type,
        command=command,
        content=content,
        url=url,
        method=method,
        headers=headers,
        body=body,
    )
    return HookDefinition(
        name=name, event=event, action=action, timeout=timeout,
    )


class TestRunCommand:
    @pytest.mark.asyncio
    async def test_successful_command(self):
        hook = make_hook(command="echo hello")
        result = await run_command(hook, make_ctx())
        assert result.success is True
        assert result.action_type == "command"
        assert result.executed is True
        assert "hello" in (result.output or "")

    @pytest.mark.asyncio
    async def test_failed_command(self):
        hook = make_hook(command="exit 1")
        result = await run_command(hook, make_ctx())
        assert result.success is False

    @pytest.mark.asyncio
    async def test_empty_command(self):
        hook = make_hook(command="")
        result = await run_command(hook, make_ctx())
        assert result.executed is True

    @pytest.mark.asyncio
    async def test_command_with_output(self):
        hook = make_hook(command="echo line1 && echo line2")
        result = await run_command(hook, make_ctx())
        assert result.success is True
        assert "line1" in (result.output or "")
        assert "line2" in (result.output or "")

    @pytest.mark.asyncio
    async def test_nonexistent_command(self):
        hook = make_hook(command="nonexistent_cmd_xyz_123")
        result = await run_command(hook, make_ctx())
        assert result.success is False
        assert result.executed is True


class TestRunPrompt:
    def test_returns_content_as_output(self):
        hook = make_hook(action_type="prompt", content="hello world")
        result = run_prompt(hook, make_ctx())
        assert result.success is True
        assert result.action_type == "prompt"
        assert result.output == "hello world"

    def test_empty_content(self):
        hook = make_hook(action_type="prompt", content="")
        result = run_prompt(hook, make_ctx())
        assert result.output == ""

    def test_none_content(self):
        hook = make_hook(action_type="prompt", content=None)
        result = run_prompt(hook, make_ctx())
        assert result.output == ""


class TestRunHttp:
    @pytest.mark.asyncio
    async def test_invalid_url(self):
        hook = make_hook(action_type="http", url="not-a-valid-url")
        result = await run_http(hook, make_ctx())
        assert result.success is False
        assert result.action_type == "http"

    @pytest.mark.asyncio
    async def test_unreachable_host(self):
        hook = make_hook(action_type="http", url="http://127.0.0.1:1/nonexistent", timeout=1.0)
        result = await run_http(hook, make_ctx())
        assert result.success is False


class TestRunAgent:
    @pytest.mark.asyncio
    async def test_placeholder(self):
        hook = make_hook(action_type="agent")
        result = await run_agent(hook, make_ctx())
        assert result.success is True
        assert result.action_type == "agent"
        assert "not yet implemented" in (result.output or "")


class TestDispatch:
    @pytest.mark.asyncio
    async def test_dispatches_to_command(self):
        hook = make_hook(action_type="command", command="echo hi")
        result = await dispatch(hook, make_ctx())
        assert result.action_type == "command"
        assert result.success is True

    def test_dispatches_to_prompt(self):
        hook = make_hook(action_type="prompt", content="test")
        # dispatch is async but run_prompt is sync - it still works
        import asyncio
        result = asyncio.run(dispatch(hook, make_ctx()))
        assert result.action_type == "prompt"
        assert result.success is True
        assert result.output == "test"

    @pytest.mark.asyncio
    async def test_dispatches_to_agent(self):
        hook = make_hook(action_type="agent")
        result = await dispatch(hook, make_ctx())
        assert result.action_type == "agent"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_unknown_action_type(self):
        hook = make_hook(action_type="unknown_type")
        result = await dispatch(hook, make_ctx())
        assert result.success is False
        assert "unknown action type" in (result.error or "")
