"""Command handlers — one file per command."""

from opcode_cli.commands.context import CommandContext
from opcode_cli.commands.handlers.clear_handler import make_clear_command
from opcode_cli.commands.handlers.compact_handler import make_compact_command
from opcode_cli.commands.handlers.do_handler import make_do_command
from opcode_cli.commands.handlers.help_handler import make_help_command
from opcode_cli.commands.handlers.memory_handler import make_memory_command
from opcode_cli.commands.handlers.permission_handler import make_permission_command
from opcode_cli.commands.handlers.plan_handler import make_plan_command
from opcode_cli.commands.handlers.session_handler import make_session_command
from opcode_cli.commands.handlers.skill_handler import make_skill_command
from opcode_cli.commands.handlers.review_handler import make_review_command
from opcode_cli.commands.handlers.status_handler import make_status_command
from opcode_cli.commands.registry import CommandRegistry


def register_all(registry: CommandRegistry, deps: CommandContext) -> None:
    registry.register(make_help_command(deps))
    registry.register(make_compact_command(deps))
    registry.register(make_clear_command(deps))
    registry.register(make_plan_command(deps))
    registry.register(make_do_command(deps))
    registry.register(make_session_command(deps))
    registry.register(make_memory_command(deps))
    registry.register(make_permission_command(deps))
    registry.register(make_review_command(deps))
    registry.register(make_status_command(deps))
    registry.register(make_skill_command(deps))
