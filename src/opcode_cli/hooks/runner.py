from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Iterable
from typing import Any

from opcode_cli.hooks.actions import dispatch
from opcode_cli.hooks.matcher import match_condition
from opcode_cli.hooks.resolver import resolve_placeholders
from opcode_cli.hooks.types import (
    HookContext,
    HookDefinition,
    HookFireResult,
    HookResult,
)

logger = logging.getLogger(__name__)


class HookRunner:
    def __init__(
        self,
        hooks: list[HookDefinition],
        base_context: HookContext,
    ) -> None:
        self._hooks = hooks
        self._base_context = base_context
        self._fired_once: set[str] = set()
        self._persist_prompts: list[str] = []
        self._once_prompts: list[str] = []
        self._intercept: str | None = None

        # Index by event name
        self._index: dict[str, list[HookDefinition]] = {}
        for hook in hooks:
            self._index.setdefault(hook.event, []).append(hook)

    async def fire(
        self,
        event: str,
        event_data: dict | None = None,
    ) -> HookFireResult:
        hooks = self._index.get(event, [])
        if not hooks:
            return HookFireResult()

        context = HookContext(
            event=event,
            session_id=self._base_context.session_id,
            project_root=self._base_context.project_root,
            timestamp=time.time(),
            data=event_data or {},
        )

        results: list[HookResult] = []
        self._intercept = None

        for hook in hooks:
            # run_once check
            if hook.run_once and hook.name in self._fired_once:
                results.append(HookResult(
                    hook_name=hook.name, event=event,
                    triggered=True, executed=False,
                    action_type=hook.action.type, success=True,
                ))
                continue

            # Condition check
            if not match_condition(hook.condition, context.data):
                results.append(HookResult(
                    hook_name=hook.name, event=event,
                    triggered=False, executed=False,
                    action_type=hook.action.type, success=True,
                ))
                continue

            # Mark run_once
            if hook.run_once:
                self._fired_once.add(hook.name)

            # Resolve placeholders in action
            action = hook.action
            resolved_content = resolve_placeholders(action.content, context)
            resolved_command = resolve_placeholders(action.command, context)
            resolved_cwd = resolve_placeholders(action.cwd, context)
            resolved_url = resolve_placeholders(action.url, context)
            resolved_body = resolve_placeholders(action.body, context)

            # Build a resolved copy
            from opcode_cli.hooks.types import HookAction
            resolved_action = HookAction(
                type=action.type,
                command=resolved_command,
                cwd=resolved_cwd,
                env=action.env,
                content=resolved_content,
                position=action.position,
                scope=action.scope,
                url=resolved_url,
                method=action.method,
                headers=action.headers,
                body=resolved_body,
                prompt=resolve_placeholders(action.prompt, context),
                model=action.model,
                tools=action.tools,
                max_iterations=action.max_iterations,
            )
            resolved_hook = HookDefinition(
                name=hook.name,
                event=hook.event,
                action=resolved_action,
                condition=hook.condition,
                run_once=hook.run_once,
                background=hook.background,
                timeout=hook.timeout,
            )

            # Execute
            async def _do_execute(h: HookDefinition, ctx: HookContext) -> HookResult:
                start = time.perf_counter()
                try:
                    result = await dispatch(h, ctx)
                    result.duration_ms = (time.perf_counter() - start) * 1000
                    return result
                except Exception as e:
                    logger.warning(
                        f"hook '{h.name}' (event={ctx.event}): execution failed: {e}"
                    )
                    return HookResult(
                        hook_name=h.name,
                        event=ctx.event,
                        triggered=True,
                        executed=True,
                        action_type=h.action.type,
                        success=False,
                        error=str(e),
                        duration_ms=(time.perf_counter() - start) * 1000,
                    )

            if hook.background:
                asyncio.create_task(_do_execute(resolved_hook, context))
                results.append(HookResult(
                    hook_name=hook.name, event=event,
                    triggered=True, executed=True, action_type=hook.action.type,
                    success=True, output="(background)",
                ))
            else:
                result = await _do_execute(resolved_hook, context)
                results.append(result)

                # Handle prompt injection
                if hook.action.type == "prompt" and result.success and result.output:
                    if hook.event == "tool_pre_execute":
                        self._intercept = result.output
                    elif hook.action.scope == "persist":
                        self._persist_prompts.append(result.output)
                    elif hook.action.scope == "once":
                        self._once_prompts.append(result.output)

        return HookFireResult(results=results, intercept=self._intercept)

    def pending_prompts(self) -> list[str]:
        return list(self._persist_prompts)

    def consume_once_prompts(self) -> list[str]:
        prompts = list(self._once_prompts)
        self._once_prompts.clear()
        return prompts

    def clear(self) -> None:
        self._fired_once.clear()
        self._persist_prompts.clear()
        self._once_prompts.clear()
