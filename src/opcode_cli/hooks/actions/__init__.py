from opcode_cli.hooks.types import HookDefinition, HookContext, HookResult


async def dispatch(hook: HookDefinition, context: HookContext) -> HookResult:
    action_type = hook.action.type
    if action_type == "command":
        from opcode_cli.hooks.actions.command import run_command
        return await run_command(hook, context)
    elif action_type == "prompt":
        from opcode_cli.hooks.actions.prompt import run_prompt
        return run_prompt(hook, context)
    elif action_type == "http":
        from opcode_cli.hooks.actions.http_action import run_http
        return await run_http(hook, context)
    elif action_type == "agent":
        from opcode_cli.hooks.actions.agent import run_agent
        return await run_agent(hook, context)
    else:
        import logging
        logging.warning(f"unknown hook action type: {action_type}")
        return HookResult(
            hook_name=hook.name,
            event=context.event,
            triggered=True,
            executed=False,
            action_type=action_type,
            success=False,
            error=f"unknown action type: {action_type}",
        )
