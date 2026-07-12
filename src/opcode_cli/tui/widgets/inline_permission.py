from __future__ import annotations

import asyncio

from opcode_cli.tui.widgets.timeline_nodes import TimelineNode


DECISION_MAP = {
    "y": "allow_once",
    "s": "allow_session",
    "d": "dont_ask_again",
    "n": "deny",
}


class PermissionWidget(TimelineNode):
    """Inline permission confirmation node in the timeline.

    Displays the prompt, then waits for the input box to submit a y/s/d/n
    decision via Enter.  No single-key capture — the user types in the normal
    input box so they can see and change their answer before confirming.
    """

    def __init__(
        self,
        tool_name: str,
        description: str,
        future: asyncio.Future,
    ) -> None:
        super().__init__("", classes="permission")
        self._tool_name = tool_name
        self._description = description
        self._future = future
        self._done = False
        self._render_prompt()

    def _render_prompt(self) -> None:
        self.update(
            f"[dim]⏺[/dim] [bold yellow]Allow[/bold yellow] {self._tool_name}({self._description})\n"
            "[bold](y)[/bold] yes this time  "
            "[bold](s)[/bold] session  "
            "[bold](d)[/bold] don't ask again  "
            "[bold](n)[/bold] no"
        )

    def resolve(self, key: str) -> bool:
        """Attempt to resolve the permission with *key*.

        Returns True if the key was a valid decision and the future was resolved,
        False otherwise (invalid key).
        """
        if self._done:
            return False

        decision = DECISION_MAP.get(key.lower())
        if decision is None:
            return False

        self._done = True
        if not self._future.done():
            self._future.set_result(decision)
        self._show_result(decision)
        return True

    def _show_result(self, decision: str) -> None:
        if decision == "deny":
            self.update(
                f"[dim]⏺[/dim] [red]✗ Denied[/red] {self._tool_name}({self._description})"
            )
            self.add_class("permission-denied")
        else:
            label_map = {
                "allow_once": "Allowed",
                "allow_session": "Allowed (session)",
                "dont_ask_again": "Allowed (always)",
            }
            label = label_map.get(decision, "Allowed")
            self.update(
                f"[dim]⏺[/dim] [green]✓ {label}[/green] {self._tool_name}({self._description})"
            )
            self.add_class("permission-allowed")

    @property
    def is_done(self) -> bool:
        return self._done
