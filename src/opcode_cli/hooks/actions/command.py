from __future__ import annotations

import asyncio
import logging
from typing import Any

from opcode_cli.hooks.types import HookDefinition, HookContext, HookResult

logger = logging.getLogger(__name__)


async def run_command(hook: HookDefinition, context: HookContext) -> HookResult:
    command = hook.action.command or ""
    cwd = hook.action.cwd or context.project_root
    env = hook.action.env or {}
    timeout = hook.timeout

    merged_env = dict(**(env or {}))
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**__import__("os").environ, **merged_env},
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            try:
                proc.send_signal(9)  # SIGTERM on Windows
            except ProcessLookupError:
                pass
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=3.0
                )
            except asyncio.TimeoutError:
                proc.kill()
                stdout_bytes = b""
                stderr_bytes = b"timed out and killed"
        stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""

        if proc.returncode != 0 and not stderr:
            stderr = f"exit code: {proc.returncode}"

        if stderr:
            output = f"stdout:\n{stdout[:500]}\nstderr:\n{stderr[:500]}"
        else:
            output = stdout[:500]

        return HookResult(
            hook_name=hook.name,
            event=context.event,
            triggered=True,
            executed=True,
            action_type="command",
            success=proc.returncode == 0,
            output=output[:500],
        )
    except Exception as e:
        logger.warning(f"hook '{hook.name}': command execution failed: {e}")
        return HookResult(
            hook_name=hook.name,
            event=context.event,
            triggered=True,
            executed=True,
            action_type="command",
            success=False,
            error=str(e),
        )
