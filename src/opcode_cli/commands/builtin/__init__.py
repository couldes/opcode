from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.builtin.clear_cmd import make_clear_command
from opcode_cli.commands.builtin.compact_cmd import make_compact_command
from opcode_cli.commands.builtin.do_cmd import make_do_command
from opcode_cli.commands.builtin.help_cmd import make_help_command
from opcode_cli.commands.builtin.memory_cmd import make_memory_command
from opcode_cli.commands.builtin.permission_cmd import make_permission_command
from opcode_cli.commands.builtin.plan_cmd import make_plan_command
from opcode_cli.commands.builtin.session_cmd import make_session_command
from opcode_cli.commands.builtin.skill_cmd import make_skill_command
from opcode_cli.commands.builtin.status_cmd import make_status_command
from opcode_cli.commands.registry import CommandRegistry


def register_all(registry: CommandRegistry, deps: CommandDeps) -> None:
    registry.register(make_help_command(deps))
    registry.register(make_compact_command(deps))
    registry.register(make_clear_command(deps))
    registry.register(make_plan_command(deps))
    registry.register(make_do_command(deps))
    registry.register(make_session_command(deps))
    registry.register(make_memory_command(deps))
    registry.register(make_permission_command(deps))
    registry.register(make_status_command(deps))
    registry.register(make_skill_command(deps))
