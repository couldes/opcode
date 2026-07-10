from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandDeps:
    agent: object  # Agent instance
    command_registry: object  # CommandRegistry instance
    permission_checker: object | None  # PermissionChecker instance
    project_memory_dir: Path
    user_memory_dir: Path
