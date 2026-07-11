from __future__ import annotations

import json
import os
import re
from pathlib import Path

from textual.widgets import TextArea

_AT_REF_RE = re.compile(r"@([\w./\\_-]+)")
_HISTORY_DIR = ".opcode/history"
_MAX_HISTORY = 200

# Directories to skip when scanning for @ completions
_SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache"}


class OpcodeChatInput(TextArea):
    """ChatInput with @ file reference expansion and input history persistence.

    T37 — @ file references: expand @filename before submission.
    T38 — Input history: persist to .opcode/history, navigate with Up/Down.
    """

    BINDINGS = [
        ("shift+enter", "insert_newline", "New line"),
    ]

    def __init__(self, work_dir: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._work_dir = work_dir or str(Path.cwd())
        self._history: list[str] = []
        self._history_index: int = -1
        self._history_file = Path(self._work_dir) / _HISTORY_DIR / "input_history.jsonl"
        self._load_history()

    # === T38: Input History ===

    def _load_history(self) -> None:
        """Load input history from .opcode/history/input_history.jsonl."""
        try:
            if self._history_file.exists():
                lines = self._history_file.read_text(encoding="utf-8").strip().splitlines()
                for line in lines:
                    try:
                        entry = json.loads(line)
                        if isinstance(entry, dict) and "text" in entry:
                            self._history.append(entry["text"])
                    except (json.JSONDecodeError, ValueError):
                        continue
                # Keep newest first for navigation
                self._history.reverse()
        except OSError:
            pass

    def _persist_entry(self, text: str) -> None:
        """Append submitted text to history file."""
        try:
            self._history_file.parent.mkdir(parents=True, exist_ok=True)
            entry = json.dumps({"text": text}, ensure_ascii=False)
            with open(self._history_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
            # Trim to max
            if len(self._history) >= _MAX_HISTORY:
                self._history.pop(0)
            self._history.append(text)
        except OSError:
            pass

    def _navigate_history(self, direction: int) -> None:
        """Navigate history: -1 = up (older), +1 = down (newer)."""
        if not self._history:
            return
        self._history_index += direction
        self._history_index = max(-1, min(self._history_index, len(self._history) - 1))
        if self._history_index == -1:
            self.text = ""
        else:
            self.text = self._history[self._history_index]
        self.cursor_location = (0, len(self.text))

    # === T37: @ File References ===

    def expand_at_refs(self, text: str) -> str:
        """Replace @filename patterns with file contents.

        If a file is not found, the @reference is left as-is.
        Skips blacklisted directories.
        """
        def _replace_match(m: re.Match) -> str:
            rel_path = m.group(1)
            # Resolve relative to work dir
            target = Path(self._work_dir) / rel_path
            try:
                target = target.resolve()
                # Security: only allow files under work dir
                work_path = Path(self._work_dir).resolve()
                if not str(target).startswith(str(work_path)):
                    return m.group(0)  # outside workspace, skip
                if target.is_file():
                    content = target.read_text(encoding="utf-8")
                    # Keep first 200 lines to avoid flooding
                    lines = content.splitlines()
                    if len(lines) > 200:
                        lines = lines[:200]
                        lines.append("... (truncated)")
                    return "\n".join(lines)
                else:
                    return m.group(0)  # file not found, keep original
            except (OSError, ValueError):
                return m.group(0)

        return _AT_REF_RE.sub(_replace_match, text)

    def scan_files_for_at(self, prefix: str) -> list[str]:
        """Find files matching prefix for @ autocomplete.

        Returns relative paths matching the given prefix.
        """
        work_path = Path(self._work_dir).resolve()
        matches: list[str] = []
        prefix_lower = prefix.lower()

        try:
            for root, dirs, files in os.walk(str(work_path)):
                # Skip blacklisted directories
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
                for f in files:
                    if not f.endswith((".py", ".md", ".txt", ".toml", ".cfg", ".yaml", ".yml", ".json")):
                        continue
                    rel = os.path.relpath(os.path.join(root, f), str(work_path))
                    if prefix_lower in rel.lower():
                        matches.append(rel)
                        if len(matches) >= 10:
                            return matches
        except (OSError, ValueError):
            pass

        return matches

    # === Key handling ===

    async def _on_key(self, event) -> None:
        if event.key == "enter":
            event.stop()
            event.prevent_default()

            # T37: Expand @ references before submission
            expanded = self.expand_at_refs(self.text)

            # T38: Persist to history
            text = self.text.strip()
            if text:
                self._persist_entry(text)
            self._history_index = -1

            # Set expanded text and trigger submission
            if expanded != self.text:
                self.text = expanded

            action_submit = getattr(self.app, "action_submit_input", None)
            if action_submit is not None:
                action_submit()
            return

        if event.key == "tab":
            text = self.text
            if text.startswith("/"):
                event.stop()
                event.prevent_default()
                handler = getattr(self.app, "handle_tab_completion", None)
                if handler is not None:
                    handler(text, self.cursor_location)
                return

        # T38: Up/Down arrow for history navigation
        if event.key == "up":
            event.stop()
            event.prevent_default()
            self._navigate_history(-1)
            return

        if event.key == "down":
            event.stop()
            event.prevent_default()
            self._navigate_history(1)
            return

        await super()._on_key(event)

    def action_insert_newline(self) -> None:
        self.insert("\n")
