from __future__ import annotations

import re
from dataclasses import dataclass

_BLACKLIST: list[tuple[str, str]] = [
    (r"rm\s+-rf\s+/", "destructive filesystem operation (rm -rf /)"),
    (r"rm\s+-r\s+--no-preserve-root\s+/", "destructive filesystem operation"),
    (r"rm\s+-rf\s+~", "destructive home directory removal"),
    (r"rm\s+-rf\s+\$HOME", "destructive home directory removal"),
    (r"rm\s+-rf\s+/\*", "destructive filesystem operation"),
    (r"curl\s+.*\|\s*(ba)?sh", "remote script pipe to shell"),
    (r"wget\s+.*\|\s*(ba)?sh", "remote script pipe to shell"),
    (r"wget\s+.*-O\s+-\s*\|\s*(ba)?sh", "remote script pipe to shell"),
    (r"curl\s+.*\|\s*bash", "remote script pipe to shell"),
    (r"chmod\s+777\s+/", "permissive chmod on system directory"),
    (r"chmod\s+-R\s+777\s+/", "recursive permissive chmod on root"),
    (r"chmod\s+777\s+~", "permissive chmod on home"),
    (r"chown\s+-R\s+\S+\s+/", "recursive chown on root"),
    (r"mkfs\.", "filesystem formatting"),
    (r"dd\s+if=.*\s+of=/dev/", "raw write to block device"),
    (r">\s*/etc/passwd", "overwrite system passwd file"),
    (r">>\s*/etc/passwd", "append to system passwd file"),
    (r">\s*/etc/shadow", "overwrite system shadow file"),
    (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "fork bomb pattern"),
    (r"git\s+push\s+.*--force.*(main|master)", "force push to main/master branch"),
    (r"git\s+push\s+.*-f\s+.*(main|master)", "force push to main/master branch"),
    (r"git\s+push\s+--force\s+origin\s+(main|master)", "force push to protected branch"),
    (r">\s*/dev/null.*rm", "suspicious /dev/null redirect"),
]


@dataclass
class _CompiledPattern:
    pattern: str
    description: str
    compiled: re.Pattern | None = None

    def __post_init__(self) -> None:
        if self.compiled is None:
            self.compiled = re.compile(self.pattern, re.IGNORECASE)

    def match(self, command: str) -> bool:
        return self.compiled is not None and self.compiled.search(command) is not None


class DangerousCommandDetector:
    """Layer 1b: detect dangerous shell commands via regex blacklist."""

    def __init__(self) -> None:
        self._patterns: list[_CompiledPattern] = [
            _CompiledPattern(pattern=p, description=d) for p, d in _BLACKLIST
        ]

    def detect(self, command: str) -> tuple[bool, str | None]:
        for cp in self._patterns:
            if cp.match(command):
                return True, f"blocked by safety policy: {cp.description}"
        return False, None
