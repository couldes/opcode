from __future__ import annotations

from opcode_cli.commands.context import CommandContext
from opcode_cli.commands.registry import Command


def make_memory_command(deps: CommandContext) -> Command:
    def handler(args: str) -> str:
        lines: list[str] = ["[bold]Memory Index[/bold]", ""]

        for label, base_dir in [
            ("Project", deps.project_memory_dir),
            ("User", deps.user_memory_dir),
        ]:
            index_path = base_dir / "MEMORY.md"
            if not index_path.exists():
                lines.append(f"[bold]{label}:[/bold] (no memories)")
            else:
                try:
                    content = index_path.read_text(encoding="utf-8").strip()
                    entry_lines = [
                        l for l in content.splitlines() if l.strip()
                    ]
                    lines.append(
                        f"[bold]{label}:[/bold] {len(entry_lines)} entries"
                    )
                    for entry in entry_lines[-5:]:
                        lines.append(f"  {entry}")
                except Exception:
                    lines.append(
                        f"[bold]{label}:[/bold] (failed to read)"
                    )
            lines.append("")

        return "\n".join(lines)

    return Command(
        name="memory",
        aliases=["mem"],
        description="Show memory status",
        usage="/memory",
        cmd_type="local",
        arg_hint=None,
        hidden=False,
        handler=handler,
    )
