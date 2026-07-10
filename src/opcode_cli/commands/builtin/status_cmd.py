from __future__ import annotations

from opcode_cli.commands.builtin._deps import CommandDeps
from opcode_cli.commands.registry import Command


def make_status_command(deps: CommandDeps) -> Command:
    def handler(args: str) -> str:
        agent = deps.agent
        usage = deps.agent.tracker.summary if hasattr(deps.agent, "tracker") else {}
        input_tokens = usage.get("input_tokens", 0) if usage else 0
        output_tokens = usage.get("output_tokens", 0) if usage else 0
        hit_rate = usage.get("hit_rate", 0) if usage else 0

        plan_mode = agent.plan_mode
        mode = "PLAN" if (plan_mode and plan_mode.in_plan) else "DEFAULT"

        archiver = getattr(agent, "_archiver", None)
        session_id = archiver._session_id if archiver else "unknown"

        msg_count = len(agent.messages)

        ctx_mgr = getattr(agent, "_context_manager", None)
        ctx_total = 0
        if ctx_mgr:
            ctx_total = ctx_mgr.estimator.estimate(agent.messages)

        lines = [
            "[bold]Agent Status[/bold]",
            f"  Mode:       {mode}",
            f"  Messages:   {msg_count}",
            f"  Tokens:     {input_tokens:,} in / {output_tokens:,} out",
            f"  Est. total: {ctx_total:,} tokens",
            f"  Session:    {session_id}",
        ]
        return "\n".join(lines)

    return Command(
        name="status",
        aliases=["st"],
        description="Show agent status",
        usage="/status",
        cmd_type="local",
        arg_hint=None,
        hidden=False,
        handler=handler,
    )
