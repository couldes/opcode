from __future__ import annotations

from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.controller import UiController
from opcode_cli.commands.registry import Command
from opcode_cli.permission.mode import PermissionMode


_VALID_MODES = {"strict", "default", "accept-edits", "permissive"}


def make_permission_command(deps: CommandDeps) -> Command:
    async def handler(args: str, ui: UiController) -> None:
        checker = deps.permission_checker
        if checker is None:
            await ui.display_message(
                "[dim]Permission: checker not available[/dim]"
            )
            return

        if not args:
            mode = checker._mode.value
            rules_count = len(checker._base_rules._rules) if checker._base_rules else 0
            await ui.display_message(
                f"[bold]Permission mode:[/bold] {mode}\n"
                f"[bold]Base rules:[/bold] {rules_count}"
            )
        else:
            mode_key = args.strip().lower()
            if mode_key not in _VALID_MODES:
                await ui.display_message(
                    f"[dim]Invalid mode '{mode_key}'. "
                    f"Valid: {', '.join(sorted(_VALID_MODES))}[/dim]"
                )
                return
            checker._mode = PermissionMode(mode_key)
            await ui.refresh_status()
            await ui.display_message(
                f"[dim]Permission mode changed to [bold]{mode_key}[/bold][/dim]"
            )

    return Command(
        name="permission",
        aliases=["perm"],
        description="Show or change permission mode",
        usage="/permission [mode]",
        cmd_type="ui",
        arg_hint="strict|default|accept-edits|permissive",
        hidden=False,
        handler=handler,
    )
