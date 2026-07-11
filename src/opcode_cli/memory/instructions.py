from __future__ import annotations

import re
from pathlib import Path

_INCLUDE_RE = re.compile(r"(?<!\S)@include\s+(\S+)")
_CODE_FENCE_RE = re.compile(r"```")


def process_includes(body: str, base_dir: str | Path) -> str:
    """Process @include directives in text.

    Replaces ``@include path/to/file.md`` with the file content.
    Skips @include directives that appear inside code fences (```...```).
    """
    base = Path(base_dir)
    lines = body.splitlines()
    result: list[str] = []
    in_fence = False

    for line in lines:
        # Track code fence state
        if _CODE_FENCE_RE.search(line):
            in_fence = not in_fence

        if not in_fence:
            def _replace_match(m: re.Match) -> str:
                rel_path = m.group(1)
                target = (base / rel_path).resolve()
                try:
                    if target.is_file():
                        return target.read_text(encoding="utf-8")
                    else:
                        return f"<!-- @include not found: {rel_path} -->"
                except (OSError, ValueError):
                    return f"<!-- @include error: {rel_path} -->"

            line = _INCLUDE_RE.sub(_replace_match, line)

        result.append(line)

    return "\n".join(result)
