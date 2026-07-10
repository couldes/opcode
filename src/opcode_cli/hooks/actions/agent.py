from __future__ import annotations

from opcode_cli.hooks.types import HookDefinition, HookContext, HookResult


async def run_agent(hook: HookDefinition, context: HookContext) -> HookResult:
    return HookResult(
        hook_name=hook.name,
        event=context.event,
        triggered=True,
        executed=True,
        action_type="agent",
        success=True,
        output="[subagent not yet implemented]",
    )
