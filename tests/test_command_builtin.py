import pytest
from pathlib import Path

from opcode_cli.commands import CommandRegistry, dispatch, ParsedCommand, parse
from opcode_cli.commands.handlers import register_all
from opcode_cli.commands.context import CommandContext
from opcode_cli.commands.handlers.help_handler import make_help_command
from opcode_cli.commands.handlers.review_handler import make_review_command
from opcode_cli.commands.handlers.plan_handler import make_plan_command
from opcode_cli.commands.handlers.do_handler import make_do_command
from opcode_cli.commands.handlers.clear_handler import make_clear_command
from opcode_cli.commands.handlers.status_handler import make_status_command
from opcode_cli.commands.handlers.memory_handler import make_memory_command


class MockUi:
    """Minimal mock UiController for testing built-in commands."""

    def __init__(self):
        self.messages = []
        self.sent = []
        self.mode = "DEFAULT"

    async def display_message(self, text: str) -> None:
        self.messages.append(text)

    async def send_to_agent(self, text: str) -> None:
        self.sent.append(text)

    def switch_mode(self, mode: str) -> None:
        self.mode = mode

    def get_mode(self) -> str:
        return self.mode

    def get_token_usage(self) -> dict | None:
        return None

    def get_session_id(self) -> str:
        return "test-session-id"

    async def refresh_status(self) -> None:
        pass

    async def clear_chat(self) -> None:
        self.messages.append("--cleared--")


class MockTracker:
    @property
    def summary(self):
        return {"input_tokens": 500, "output_tokens": 200}


class MockArchiver:
    _session_id = "20260710-120000-ab12"


class MockAgent:
    def __init__(self):
        self.messages = []
        self.tracker = MockTracker()
        self.plan_mode = None
        self._archiver = MockArchiver()


@pytest.fixture
def deps():
    reg = CommandRegistry()
    return CommandContext(
        agent=MockAgent(),
        command_registry=reg,
        permission_checker=None,
        project_memory_dir=Path("/tmp"),
        user_memory_dir=Path("/tmp"),
    )


class TestHelpCommand:
    def test_output_contains_help_text(self, deps):
        cmd = make_help_command(deps)
        deps.command_registry.register(cmd)
        result = cmd.handler("")
        assert "Commands:" in result
        assert "/help" in result


class TestReviewCommand:
    def test_no_args(self, deps):
        cmd = make_review_command(deps)
        result = cmd.handler("")
        assert "Review" in result
        assert "Focus on" not in result

    def test_with_args(self, deps):
        cmd = make_review_command(deps)
        result = cmd.handler("security")
        assert "Focus on security" in result


class TestPlanCommand:
    @pytest.mark.asyncio
    async def test_switches_mode(self, deps):
        cmd = make_plan_command(deps)
        ui = MockUi()
        await cmd.handler("", ui)
        assert ui.mode == "plan"
        assert any("plan mode" in m.lower() for m in ui.messages)


class TestDoCommand:
    @pytest.mark.asyncio
    async def test_switches_mode(self, deps):
        cmd = make_do_command(deps)
        ui = MockUi()
        await cmd.handler("", ui)
        assert ui.mode == "default"
        assert any("do mode" in m.lower() for m in ui.messages)


class TestClearCommand:
    @pytest.mark.asyncio
    async def test_clears_chat(self, deps):
        cmd = make_clear_command(deps)
        ui = MockUi()
        await cmd.handler("", ui)
        assert "--cleared--" in ui.messages


class TestStatusCommand:
    def test_contains_info(self, deps):
        cmd = make_status_command(deps)
        result = cmd.handler("")
        assert "DEFAULT" in result or "PLAN" in result
        assert "Messages:" in result
        assert "Session:" in result


class TestMemoryCommand:
    def test_no_memories(self, deps):
        cmd = make_memory_command(deps)
        result = cmd.handler("")
        assert "Memory Index" in result
        # No memory files exist at /tmp -> should show "(no memories)"


class TestRegisterAll:
    def test_registers_11_commands(self, deps):
        reg = CommandRegistry()
        register_all(reg, deps)
        visible = reg.list_visible()
        assert len(visible) == 11
        names = {c.name for c in visible}
        expected = {"help", "compact", "clear", "plan", "do", "session",
                    "memory", "permission", "status", "skill", "review"}
        assert names == expected


class TestDispatcher:
    @pytest.mark.asyncio
    async def test_local_command(self, deps):
        reg = CommandRegistry()
        cmd = make_help_command(deps)
        reg.register(cmd)
        ui = MockUi()
        parsed = parse("/help", reg)
        assert parsed is not None
        await dispatch(parsed, ui)
        assert len(ui.messages) == 1
        assert "Commands:" in ui.messages[0]

    @pytest.mark.asyncio
    async def test_prompt_command(self, deps):
        reg = CommandRegistry()
        cmd = make_review_command(deps)
        reg.register(cmd)
        ui = MockUi()
        parsed = parse("/review security", reg)
        assert parsed is not None
        await dispatch(parsed, ui)
        assert len(ui.sent) == 1
        assert "security" in ui.sent[0]
