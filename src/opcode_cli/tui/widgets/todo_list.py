from __future__ import annotations

from opcode_cli.tui.widgets.timeline_nodes import TimelineNode


class TodoListNode(TimelineNode):
    """Checkable todo list reflecting multi-step plan progress."""

    def __init__(self, items: list[dict] | None = None) -> None:
        super().__init__("", classes="todo-list")
        self._items: list[dict] = list(items) if items else []

    def on_mount(self) -> None:
        self._update_display()

    def update_items(self, items: list[dict]) -> None:
        self._items = list(items)
        self._update_display()

    def _update_display(self) -> None:
        if not self._items:
            self.update("")
            return
        lines = ["[bold]Tasks:[/bold]"]
        for item in self._items:
            label = item.get("label", "")
            done = item.get("done", False)
            if done:
                lines.append(f"[green]☑[/green] [dim]{label}[/dim]")
            else:
                lines.append(f"[dim]☐[/dim] {label}")
        self.update("\n".join(lines))
