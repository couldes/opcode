from __future__ import annotations

import logging

import httpx

from opcode_cli.hooks.types import HookDefinition, HookContext, HookResult

logger = logging.getLogger(__name__)


async def run_http(hook: HookDefinition, context: HookContext) -> HookResult:
    url = hook.action.url or ""
    method = hook.action.method or "POST"
    headers = hook.action.headers or {}
    body = hook.action.body or ""
    timeout = hook.timeout

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body if body else None,
            )
            output = response.text[:500] if response.text else ""
            return HookResult(
                hook_name=hook.name,
                event=context.event,
                triggered=True,
                executed=True,
                action_type="http",
                success=200 <= response.status_code < 300,
                output=output,
            )
    except httpx.TimeoutException:
        logger.warning(f"hook '{hook.name}': HTTP timeout after {timeout}s")
        return HookResult(
            hook_name=hook.name,
            event=context.event,
            triggered=True,
            executed=True,
            action_type="http",
            success=False,
            error=f"timeout after {timeout}s",
        )
    except Exception as e:
        logger.warning(f"hook '{hook.name}': HTTP request failed: {e}")
        return HookResult(
            hook_name=hook.name,
            event=context.event,
            triggered=True,
            executed=True,
            action_type="http",
            success=False,
            error=str(e),
        )
