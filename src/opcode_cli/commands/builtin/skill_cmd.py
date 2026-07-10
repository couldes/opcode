from __future__ import annotations

from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.registry import Command


def make_skill_command(deps: CommandDeps) -> Command:
    def handler(args: str) -> str:
        manager = deps.skills_manager
        if not manager:
            return "Skills system not available."

        active_names = set(manager.get_active_names())
        skills = manager._registry.list_all()

        if not skills:
            return "No skills available."

        lines = ["Available skills:"]
        for s in sorted(skills, key=lambda x: x.name):
            status = " [ACTIVE]" if s.name in active_names else ""
            source = ""
            if s.directory_path:
                source = " (directory)"
            lines.append(f"  /{s.name:<12} {s.description}{status}{source}")
        return "\n".join(lines)

    return Command(
        name="skill",
        description="List all available skills and their status",
        usage="/skill",
        cmd_type="local",
        hidden=False,
        handler=handler,
    )
