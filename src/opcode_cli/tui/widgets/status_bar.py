from __future__ import annotations

import os

from textual.widgets import Static


class StatusBar(Static):
    """Bottom status bar showing mode and token usage."""

    def __init__(self) -> None:
        super().__init__("", id="status-bar")
        self.can_focus = False
        self._mode = "DEFAULT"
        self._token_count = 0
        self._render_bar()

    def _render_bar(self) -> None:
        token_str = f"{self._token_count} tokens" if self._token_count else ""
        try:
            width = os.get_terminal_size().columns
        except OSError:
            width = 80
        left = f" {self._mode} "
        right = f" {token_str} " if token_str else ""
        padding = max(1, width - len(left) - len(right))
        self.update(f"[reverse]{left}{' ' * padding}{right}[/reverse]")

    def update_mode(self, mode: str) -> None:
        self._mode = mode
        self._render_bar()

    def update_tokens(self, n: int) -> None:
        self._token_count = n
        self._render_bar()
