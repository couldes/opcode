from __future__ import annotations

from opcode_cli.hooks.types import HookDefinition, HookContext, HookResult


def run_prompt(hook: HookDefinition, context: HookContext) -> HookResult:
    content = hook.action.content or ""
    return HookResult(
        hook_name=hook.name,
        event=context.event,
        triggered=True,
        executed=True,
        action_type="prompt",
        success=True,
        output=content,
    )
