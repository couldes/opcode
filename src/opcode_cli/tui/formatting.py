from __future__ import annotations

import json
from pathlib import Path


def format_tool_call(name: str, input_json: str) -> str:
    """Format a tool call for display — compact single-line with key param."""
    try:
        params = json.loads(input_json)
    except json.JSONDecodeError:
        return f"[dim]⏺[/dim] {name}"

    if name in ("Read", "Write", "Edit") and "file_path" in params:
        filename = Path(params["file_path"]).name
        return f"[dim]⏺[/dim] {name} [dim]{filename}[/dim]"

    if name == "Bash" and "command" in params:
        cmd = params["command"]
        if len(cmd) > 60:
            cmd = cmd[:57] + "..."
        return f"[dim]⏺[/dim] Bash [dim]{cmd}[/dim]"

    if name in ("Grep", "Glob") and "pattern" in params:
        return f"[dim]⏺[/dim] {name} [dim]{params['pattern']}[/dim]"

    if name == "Agent" and "description" in params:
        desc = params["description"]
        if len(desc) > 50:
            desc = desc[:47] + "..."
        return f"[dim]⏺[/dim] Agent [dim]{desc}[/dim]"

    items = list(params.items())
    if items:
        val = str(items[0][1])
        if len(val) > 40:
            val = val[:37] + "..."
        return f"[dim]⏺[/dim] {name} [dim]{items[0][0]}={val}[/dim]"
    return f"[dim]⏺[/dim] {name}"


def format_tool_result(name: str, success: bool, content: str, error: str | None = None) -> str:
    """Format a tool result summary line."""
    icon = "[green]✓[/green]" if success else "[red]✗[/red]"

    if not success and error:
        err = error.strip()
        if len(err) > 60:
            err = err[:57] + "..."
        return f"[dim]⎿[/dim] {icon} [dim]{err}[/dim]"

    if success and content:
        lines = content.strip().splitlines()
        return f"[dim]⎿[/dim] {icon} [dim]· {len(lines)} lines[/dim]"

    if not success:
        return f"[dim]⎿[/dim] {icon} [dim]error[/dim]"

    return f"[dim]⎿[/dim] {icon}"


def format_diff(content: str, max_lines: int = 5) -> str | None:
    """Extract +/- lines from edit content for compact diff display."""
    added: list[str] = []
    removed: list[str] = []

    for line in content.strip().splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line)
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line)

    if not added and not removed:
        return None

    parts: list[str] = []
    for r in removed[:max_lines]:
        parts.append(f"[red]{r}[/red]")
    for a in added[:max_lines]:
        parts.append(f"[green]{a}[/green]")

    total = len(added) + len(removed)
    suffix = f"\n[dim]… {total} change lines[/dim]" if total > max_lines else ""
    return "\n".join(parts) + suffix


def format_result_detail(content: str, max_lines: int = 5) -> tuple[str, int]:
    """Return (preview_text, total_lines) for expandable result display."""
    lines = content.strip().splitlines()
    n = len(lines)
    if n <= max_lines:
        return content.strip(), n
    preview = "\n".join(lines[:max_lines])
    return f"{preview}\n[dim]… {n - max_lines} more lines (Enter to expand)[/dim]", n
