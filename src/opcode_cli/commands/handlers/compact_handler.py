from __future__ import annotations

from opcode_cli.commands.context import CommandContext
from opcode_cli.commands.controller import UiController
from opcode_cli.commands.registry import Command


def make_compact_command(deps: CommandContext) -> Command:
    async def handler(args: str, ui: UiController) -> None:
        decision = await deps.agent.compact_manual()
        if decision is None:
            await ui.display_message(
                "[dim]Compression: context manager not available[/dim]"
            )
            return

        parts = []
        if decision.did_offload:
            parts.append(f"offloaded {decision.offloaded_count} tool results")
        if decision.did_summarize:
            after = deps.agent._context_manager.estimator.estimate(
                deps.agent.messages
            )
            parts.append(
                f"summarized {decision.summarized_count} messages "
                f"({decision.total_tokens // 1000}K -> {after // 1000}K tokens)"
            )
        if decision.summary_broken:
            parts.append("summarizer broken after 3 failures")
        if not parts:
            parts.append("no compression needed")

        await ui.display_message(f"[dim]Compression: {', '.join(parts)}[/dim]")

    return Command(
        name="compact",
        aliases=["compress"],
        description="Compress conversation context",
        usage="/compact",
        cmd_type="ui",
        arg_hint=None,
        hidden=False,
        handler=handler,
    )
