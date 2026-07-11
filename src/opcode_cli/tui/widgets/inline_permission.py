from __future__ import annotations

import asyncio

from textual.widgets import Static


class PermissionWidget(Static):
    """Inline permission confirmation widget.

    Mounts into the chat flow, captures y/s/n/d keyboard input,
    resolves the attached Future, then removes itself.
    """

    def __init__(
        self,
        tool_name: str,
        description: str,
        future: asyncio.Future,
    ) -> None:
        super().__init__("")
        self._tool_name = tool_name
        self._description = description
        self._future = future
        self._done = False

    def on_mount(self) -> None:
        self._render_prompt()

    def _render_prompt(self) -> None:
        self.update(
            f"[bold yellow]Allow[/bold yellow] {self._tool_name}({self._description})\n"
            "[bold](y)[/bold] yes this time  "
            "[bold](s)[/bold] session  "
            "[bold](d)[/bold] don't ask again  "
            "[bold](n)[/bold] no"
        )

    def _on_key(self, event) -> None:
        if self._done:
            return

        key = event.key.lower()
        decision_map = {
            "y": "allow_once",
            "s": "allow_session",
            "d": "dont_ask_again",
            "n": "deny",
        }

        if key in decision_map:
            event.stop()
            event.prevent_default()
            self._done = True
            decision = decision_map[key]
            if not self._future.done():
                self._future.set_result(decision)
            # Remove self after a brief pause so user sees the choice
            asyncio.ensure_future(self._remove_after_delay())

    async def _remove_after_delay(self) -> None:
        await asyncio.sleep(0.1)
        try:
            await self.remove()
        except Exception:
            pass
