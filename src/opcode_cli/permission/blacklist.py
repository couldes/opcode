import re

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

_COMPILED: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE), description)
    for pattern, description in _BLACKLIST
]


def check_command(command: str) -> tuple[bool, str | None]:
    for pattern, description in _COMPILED:
        if pattern.search(command):
            return True, f"blocked by safety policy: {description}"
    return False, None
