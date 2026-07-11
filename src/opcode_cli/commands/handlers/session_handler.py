from __future__ import annotations

from opcode_cli.commands.context import CommandContext
from opcode_cli.commands.controller import UiController
from opcode_cli.commands.registry import Command


def make_session_command(deps: CommandContext) -> Command:
    async def handler(args: str, ui: UiController) -> None:
        archiver = getattr(deps.agent, "_archiver", None)
        if archiver is None:
            await ui.display_message(
                "[dim]Session: archiver not available[/dim]"
            )
            return

        from opcode_cli.session.index import list_sessions

        if not args:
            sessions = list_sessions(archiver._dir, limit=10)
            if not sessions:
                await ui.display_message("[dim]No saved sessions found[/dim]")
                return
            lines = ["[bold]Recent sessions:[/bold]"]
            for s in sessions:
                date_str = s.created_at.strftime("%Y-%m-%d %H:%M")
                lines.append(
                    f"  [cyan]{s.id}[/cyan] -- {s.title[:60]} -- "
                    f"{date_str} -- {s.message_count} messages"
                )
            await ui.display_message("\n".join(lines))
        else:
            from opcode_cli.session.index import session_exists

            if not session_exists(archiver._dir, args):
                await ui.display_message(
                    f"[dim]Session {args} not found[/dim]"
                )
                return

            if len(deps.agent.messages) > 1:
                await ui.display_message(
                    "[dim]Loading session... (current unsaved context will be lost)[/dim]"
                )

            warnings = await deps.agent.load_session(args)
            if warnings:
                for w in warnings:
                    await ui.display_message(f"[dim]{w}[/dim]")

            await ui.display_message(
                f"[dim]Session {args} restored "
                f"({len(deps.agent.messages)} messages)[/dim]\n"
                f"[dim]Type /do to continue working.[/dim]"
            )

    return Command(
        name="session",
        aliases=["sess"],
        description="Show or load saved sessions",
        usage="/session [id]",
        cmd_type="ui",
        arg_hint="session_id",
        hidden=False,
        handler=handler,
    )
